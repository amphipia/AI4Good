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

from detectors.qr_detector import (
    detect_qr_codes,
    blur_selected_qr_codes,
)


router = APIRouter()


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

MAX_FILE_SIZE = 10 * 1024 * 1024

def classify_qr_content(value: str) -> str:
    """
    Basic classification of decoded QR content.
    """

    if not value:
        return "Unknown / undecoded"

    value_lower = value.lower().strip()

    if (
        value_lower.startswith("http://")
        or value_lower.startswith("https://")
    ):
        return "Web address"

    if value_lower.startswith("mailto:"):
        return "Email address"

    if value_lower.startswith("tel:"):
        return "Phone number"

    if value_lower.startswith("wifi:"):
        return "Wi-Fi information"

    if value_lower.startswith("sms:"):
        return "SMS message"

    if value_lower.startswith("geo:"):
        return "Location"

    return "Other content"

async def save_upload_temporarily(
    file: UploadFile
) -> Path:
    """
    Save uploaded image temporarily.
    The caller must delete the file afterward.
    """

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported image type. "
                "Please upload a JPEG or PNG image."
            ),
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image is larger than the 10 MB limit.",
        )

    suffix = ALLOWED_IMAGE_TYPES[
        file.content_type
    ]

    fd, temp_path = tempfile.mkstemp(
        prefix="privchk_qr_",
        suffix=suffix,
    )

    os.close(fd)

    path = Path(temp_path)

    path.write_bytes(contents)

    return path


# ---------------------------------------------------------
# QR SCAN
# ---------------------------------------------------------

@router.post("/scan")
async def scan_qr_codes(
    file: UploadFile = File(...)
):
    """
    Detect QR codes in an uploaded image.
    """

    temp_path = None

    try:
        temp_path = await save_upload_temporarily(
            file
        )

        result = detect_qr_codes(
            temp_path
        )

        qr_codes = []

        for qr in result["qr_codes"]:

            decoded = qr.get(
                "decoded",
                ""
            )

            qr_codes.append({
                "decoded": decoded,
                "decoded_available": bool(decoded),
                "content_type":
                    classify_qr_content(decoded),
                "points": qr["points"],
            })

        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "qr_count": len(qr_codes),
            "qr_codes": qr_codes,
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
                f"QR detection failed: {exc}"
            ),
        )

    finally:
        if (
            temp_path
            and temp_path.exists()
        ):
            temp_path.unlink()


# ---------------------------------------------------------
# QR SANITIZE
# ---------------------------------------------------------

@router.post("/sanitize")
async def sanitize_qr_codes(
    file: UploadFile = File(...),

    selected_qr_codes: str = Form("[]"),
):
    """
    Blur only selected QR regions.
    """

    input_path = None
    output_path = None

    try:

        # Convert JSON string sent by frontend
        try:
            qr_codes = json.loads(
                selected_qr_codes
            )

        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_qr_codes must "
                    "be valid JSON."
                ),
            )

        if not isinstance(
            qr_codes,
            list
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_qr_codes must "
                    "be a list."
                ),
            )

        # Validate coordinate structure
        validated_qr_codes = []

        for qr in qr_codes:

            if not isinstance(
                qr,
                dict
            ):
                continue

            points = qr.get(
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
                    "x": int(
                        point["x"]
                    ),
                    "y": int(
                        point["y"]
                    ),
                })

            # QR normally has 4 corner points
            if len(
                validated_points
            ) >= 4:

                validated_qr_codes.append({
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
                    "privchk_qr_safe_"
                ),
                suffix=suffix,
            )
        )

        os.close(fd)

        output_path = Path(
            output_name
        )

        result = (
            blur_selected_qr_codes(
                input_path,
                output_path,
                validated_qr_codes,
            )
        )

        safe_image_bytes = (
            output_path.read_bytes()
        )

        if suffix == ".jpg":

            media_type = "image/jpeg"

            download_name = (
                "privchk_qr_safe.jpg"
            )

        else:

            media_type = "image/png"

            download_name = (
                "privchk_qr_safe.png"
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

                "X-PrivChk-QR-Blurred":
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
                "QR sanitization failed: "
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