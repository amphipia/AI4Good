import os
import tempfile
import json
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import Response

from detectors.face_detector import (
    detect_faces,
    blur_selected_faces,
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
    """
    Save an uploaded image to a temporary file.
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
        prefix="privchk_face_",
        suffix=suffix,
    )

    os.close(fd)

    path = Path(temp_path)

    path.write_bytes(contents)

    return path


# ---------------------------------------------------------
# FACE SCAN
# ---------------------------------------------------------

@router.post("/scan")
async def scan_faces(
    file: UploadFile = File(...)
):
    """
    Detect possible human faces in an uploaded image.
    """

    temp_path = None

    try:

        temp_path = await (
            save_upload_temporarily(file)
        )

        result = detect_faces(
            temp_path
        )

        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "face_count": result["face_count"],
            "faces": result["faces"],
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
                f"Face detection failed: {exc}"
            ),
        )

    finally:

        if (
            temp_path
            and temp_path.exists()
        ):
            temp_path.unlink()


# ---------------------------------------------------------
# FACE SANITIZE
# ---------------------------------------------------------

@router.post("/sanitize")
async def sanitize_faces(
    file: UploadFile = File(...),

    selected_faces: str = Form("[]"),
):
    """
    Blur only the selected face regions.
    """

    input_path = None
    output_path = None

    try:

        # Parse selected faces sent by frontend
        try:

            faces = json.loads(
                selected_faces
            )

        except json.JSONDecodeError:

            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_faces must be "
                    "valid JSON."
                ),
            )

        if not isinstance(
            faces,
            list
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_faces must "
                    "be a list."
                ),
            )

        # Basic validation
        validated_faces = []

        required_fields = {
            "x",
            "y",
            "width",
            "height",
        }

        for face in faces:

            if not isinstance(
                face,
                dict
            ):
                continue

            if not required_fields.issubset(
                face.keys()
            ):
                continue

            validated_faces.append({
                "x": int(face["x"]),
                "y": int(face["y"]),
                "width": int(
                    face["width"]
                ),
                "height": int(
                    face["height"]
                ),
            })

        input_path = await (
            save_upload_temporarily(file)
        )

        suffix = ALLOWED_IMAGE_TYPES[
            file.content_type
        ]

        fd, output_name = tempfile.mkstemp(
            prefix="privchk_faces_safe_",
            suffix=suffix,
        )

        os.close(fd)

        output_path = Path(
            output_name
        )

        result = blur_selected_faces(
            input_path,
            output_path,
            validated_faces,
        )

        safe_image_bytes = (
            output_path.read_bytes()
        )

        if suffix == ".jpg":

            media_type = "image/jpeg"

            download_name = (
                "privchk_faces_safe.jpg"
            )

        else:

            media_type = "image/png"

            download_name = (
                "privchk_faces_safe.png"
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

                "X-PrivChk-Faces-Blurred":
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
                "Face sanitization failed: "
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