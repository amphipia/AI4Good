import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import UnidentifiedImageError

from detectors.metadata_detector import (
    scan_metadata,
    create_safe_copy,
    get_display_metadata,
)


router = APIRouter()


# For the MVP, support formats we know our sanitizer handles well.
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def save_upload_temporarily(
    file: UploadFile
) -> Path:
    """
    Save an uploaded image to a temporary file.

    The caller is responsible for deleting the file.
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

    suffix = ALLOWED_IMAGE_TYPES[file.content_type]

    fd, temp_path = tempfile.mkstemp(
        prefix="privchk_",
        suffix=suffix,
    )

    os.close(fd)

    path = Path(temp_path)
    path.write_bytes(contents)

    return path


@router.post("/scan")
async def scan_image_metadata(
    file: UploadFile = File(...)
):
    """
    Scan an image for privacy-relevant metadata.
    """

    temp_path = None

    try:
        temp_path = await save_upload_temporarily(file)

        result = scan_metadata(temp_path)

        display_metadata = get_display_metadata(
            result["all_metadata"]
        )

        response = {
            "filename": file.filename,
            "content_type": file.content_type,

            "metadata_found": result["has_exif"],

            "gps_found": result["has_gps"],

            "gps": None,

            "metadata": display_metadata,
        }

        if result["has_gps"]:
            response["gps"] = {
                "latitude": result["latitude"],
                "longitude": result["longitude"],
            }

        return response

    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid image.",
        )

    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to process image: {exc}",
        )

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@router.post("/sanitize")
async def sanitize_image_metadata(
    file: UploadFile = File(...)
):
    """
    Remove metadata and return a privacy-safe copy.
    """

    input_path = None
    output_path = None

    try:
        input_path = await save_upload_temporarily(file)

        suffix = ALLOWED_IMAGE_TYPES[file.content_type]

        fd, output_name = tempfile.mkstemp(
            prefix="privchk_safe_",
            suffix=suffix,
        )

        os.close(fd)

        output_path = Path(output_name)

        created_path = create_safe_copy(
            input_path,
            output_path,
        )

        safe_image_bytes = created_path.read_bytes()

        if created_path.suffix.lower() in (
            ".jpg",
            ".jpeg",
        ):
            media_type = "image/jpeg"
            download_name = "privchk_safe.jpg"

        else:
            media_type = "image/png"
            download_name = "privchk_safe.png"

        return Response(
            content=safe_image_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition":
                    f'attachment; filename="{download_name}"'
            },
        )

    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid image.",
        )

    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to process image: {exc}",
        )

    finally:

        if input_path and input_path.exists():
            input_path.unlink()

        if output_path and output_path.exists():
            output_path.unlink()