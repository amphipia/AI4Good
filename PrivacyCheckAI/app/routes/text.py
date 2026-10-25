import json
import os
import tempfile
import traceback

from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import Response

from detectors.text_detector import (
    detect_text,
    redact_selected_text,
)


router = APIRouter()


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

MAX_FILE_SIZE = 10 * 1024 * 1024


async def save_upload_temporarily(
    file: UploadFile
) -> Path:

    if file.content_type not in ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported image type. "
                "Please upload JPEG or PNG."
            ),
        )

    contents = await file.read()

    if not contents:

        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE:

        raise HTTPException(
            status_code=413,
            detail="Image exceeds 10 MB limit.",
        )

    suffix = ALLOWED_IMAGE_TYPES[
        file.content_type
    ]

    fd, temp_path = tempfile.mkstemp(
        prefix="privchk_text_",
        suffix=suffix,
    )

    os.close(fd)

    path = Path(
        temp_path
    )

    path.write_bytes(
        contents
    )

    return path


# ---------------------------------------------------------
# TEXT / PII SCAN
# ---------------------------------------------------------

@router.post("/scan")
async def scan_text(
    file: UploadFile = File(...)
):

    temp_path = None

    try:

        temp_path = await (
            save_upload_temporarily(
                file
            )
        )

        result = detect_text(
            temp_path
        )

        return {
            "filename":
                file.filename,

            "content_type":
                file.content_type,

            "text_count":
                result[
                    "text_count"
                ],

            "privacy_text_count":
                result[
                    "privacy_text_count"
                ],

            # Only return privacy-relevant
            # OCR regions to the normal UI.
            "privacy_items":
                result[
                    "privacy_items"
                ],
        }

    except ValueError as exc:

        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=(
                "Text detection failed: "
                f"{exc}"
            ),
        )

    finally:

        if (
            temp_path
            and temp_path.exists()
        ):
            temp_path.unlink()


# ---------------------------------------------------------
# TEXT / PII SANITIZE
# ---------------------------------------------------------

@router.post("/sanitize")
async def sanitize_text(
    file: UploadFile = File(...),

    selected_text: str = Form("[]"),
):

    input_path = None
    output_path = None

    try:

        try:

            text_items = json.loads(
                selected_text
            )

        except json.JSONDecodeError:

            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_text must "
                    "be valid JSON."
                ),
            )

        if not isinstance(
            text_items,
            list
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_text must "
                    "be a list."
                ),
            )

        validated_items = []

        for item in text_items:

            if not isinstance(
                item,
                dict
            ):
                continue

            points = item.get(
                "points"
            )

            if not isinstance(
                points,
                list
            ):
                continue

            validated_points = []

            for point in points:

                if not isinstance(
                    point,
                    dict
                ):
                    continue

                if (
                    "x" not in point
                    or "y" not in point
                ):
                    continue

                validated_points.append({
                    "x":
                        int(
                            point["x"]
                        ),

                    "y":
                        int(
                            point["y"]
                        ),
                })

            if len(
                validated_points
            ) >= 4:

                validated_items.append({
                    "points":
                        validated_points
                })

        input_path = await (
            save_upload_temporarily(
                file
            )
        )

        suffix = ALLOWED_IMAGE_TYPES[
            file.content_type
        ]

        fd, output_name = (
            tempfile.mkstemp(
                prefix=(
                    "privchk_text_safe_"
                ),
                suffix=suffix,
            )
        )

        os.close(fd)

        output_path = Path(
            output_name
        )

        result = redact_selected_text(
            input_path,
            output_path,
            validated_items,
        )

        safe_image_bytes = (
            output_path.read_bytes()
        )

        if suffix == ".jpg":

            media_type = "image/jpeg"

            download_name = (
                "privchk_safe.jpg"
            )

        else:

            media_type = "image/png"

            download_name = (
                "privchk_safe.png"
            )

        return Response(
            content=safe_image_bytes,

            media_type=media_type,

            headers={
                "Content-Disposition":
                    (
                        "attachment; "
                        f'filename="{download_name}"'
                    ),

                "X-PrivChk-Text-Redacted":
                    str(
                        result[
                            "redacted_count"
                        ]
                    ),
            },
        )

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Text sanitization failed: "
                f"{exc}"
            ),
        )

    finally:

        if (
            input_path
            and input_path.exists()
        ):
            input_path.unlink()

        if (
            output_path
            and output_path.exists()
        ):
            output_path.unlink()