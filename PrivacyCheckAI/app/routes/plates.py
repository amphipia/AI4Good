import json
import os
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import Response

from detectors.license_plate_detector import (
    detect_license_plates,
    blur_selected_plates,
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
        prefix="privchk_plate_",
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
# LICENSE PLATE SCAN
# ---------------------------------------------------------

@router.post("/scan")
async def scan_license_plates(
    file: UploadFile = File(...)
):

    temp_path = None

    try:

        temp_path = await (
            save_upload_temporarily(
                file
            )
        )

        result = detect_license_plates(
            temp_path
        )

        return {
            "filename":
                file.filename,

            "content_type":
                file.content_type,

            "plate_count":
                result["plate_count"],

            "plates":
                result["plates"],
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "License plate detection failed: "
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
# LICENSE PLATE SANITIZE
# ---------------------------------------------------------

@router.post("/sanitize")
async def sanitize_license_plates(
    file: UploadFile = File(...),

    selected_plates: str = Form("[]"),
):

    input_path = None
    output_path = None

    try:

        try:

            plates = json.loads(
                selected_plates
            )

        except json.JSONDecodeError:

            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_plates must "
                    "be valid JSON."
                ),
            )

        if not isinstance(
            plates,
            list
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_plates must "
                    "be a list."
                ),
            )

        validated_plates = []

        required_fields = {
            "x",
            "y",
            "width",
            "height",
        }

        for plate in plates:

            if not isinstance(
                plate,
                dict
            ):
                continue

            if not required_fields.issubset(
                plate.keys()
            ):
                continue

            validated_plates.append({
                "x":
                    int(
                        plate["x"]
                    ),

                "y":
                    int(
                        plate["y"]
                    ),

                "width":
                    int(
                        plate["width"]
                    ),

                "height":
                    int(
                        plate["height"]
                    ),
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
                    "privchk_plate_safe_"
                ),
                suffix=suffix,
            )
        )

        os.close(fd)

        output_path = Path(
            output_name
        )

        result = blur_selected_plates(
            input_path,
            output_path,
            validated_plates,
        )

        safe_image_bytes = (
            output_path.read_bytes()
        )

        if suffix == ".jpg":

            media_type = "image/jpeg"

            download_name = (
                "privchk_protected.jpg"
            )

        else:

            media_type = "image/png"

            download_name = (
                "privchk_protected.png"
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

                "X-PrivChk-Plates-Blurred":
                    str(
                        result[
                            "blurred_count"
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
                "License plate sanitization failed: "
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