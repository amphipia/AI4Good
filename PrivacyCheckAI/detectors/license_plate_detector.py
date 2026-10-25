from pathlib import Path

import cv2
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "license_plate_yolov8.pt"
)


CONFIDENCE_THRESHOLD = 0.15


if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"License plate model not found: {MODEL_PATH}"
    )


# Load once when module starts
model = YOLO(
    str(MODEL_PATH)
)


def detect_license_plates(image_path):
    """
    Detect license plates in an image.

    Returns:
        {
            "plate_count": int,
            "plates": [
                {
                    "x": int,
                    "y": int,
                    "width": int,
                    "height": int,
                    "confidence": float
                }
            ]
        }
    """

    image_path = Path(
        image_path
    )

    image = cv2.imread(
        str(image_path)
    )

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    results = model.predict(
        source=str(image_path),

        # Start here.
        # We can increase this later for very small plates.
        imgsz=1280,

        conf=CONFIDENCE_THRESHOLD,

        verbose=False,
    )

    plates = []

    if not results:
        return {
            "plate_count": 0,
            "plates": [],
        }

    result = results[0]

    if result.boxes is None:
        return {
            "plate_count": 0,
            "plates": [],
        }

    for box in result.boxes:

        confidence = float(
            box.conf[0].item()
        )

        x1, y1, x2, y2 = (
            box.xyxy[0]
            .cpu()
            .tolist()
        )

        x1 = int(x1)
        y1 = int(y1)
        x2 = int(x2)
        y2 = int(y2)

        width = x2 - x1
        height = y2 - y1

        if (
            width <= 0
            or height <= 0
        ):
            continue

        plates.append({
            "x": x1,
            "y": y1,
            "width": width,
            "height": height,
            "confidence": round(
                confidence,
                4
            ),
        })

    plates.sort(
        key=lambda plate:
            plate["confidence"],
        reverse=True
    )

    return {
        "plate_count":
            len(plates),

        "plates":
            plates,
    }


def draw_license_plates(
    input_path,
    output_path
):
    """
    Draw boxes around detected plates.
    Development/testing only.
    """

    input_path = Path(
        input_path
    )

    output_path = Path(
        output_path
    )

    image = cv2.imread(
        str(input_path)
    )

    if image is None:
        raise ValueError(
            f"Could not read image: {input_path}"
        )

    result = detect_license_plates(
        input_path
    )

    for index, plate in enumerate(
        result["plates"],
        start=1
    ):

        x = plate["x"]
        y = plate["y"]
        w = plate["width"]
        h = plate["height"]

        confidence = (
            plate["confidence"]
        )

        cv2.rectangle(
            image,
            (x, y),
            (x + w, y + h),
            (255, 0, 255),
            3
        )

        cv2.putText(
            image,
            (
                f"Plate {index}: "
                f"{confidence:.2f}"
            ),
            (
                x,
                max(
                    25,
                    y - 8
                )
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 0, 255),
            2
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    success = cv2.imwrite(
        str(output_path),
        image
    )

    if not success:
        raise ValueError(
            f"Could not save image: {output_path}"
        )

    return result

def blur_selected_plates(
    input_path,
    output_path,
    plates,
):
    """
    Blur selected license plate regions.
    """

    input_path = Path(
        input_path
    )

    output_path = Path(
        output_path
    )

    image = cv2.imread(
        str(input_path)
    )

    if image is None:
        raise ValueError(
            f"Could not read image: {input_path}"
        )

    image_height, image_width = (
        image.shape[:2]
    )

    blurred_count = 0

    for plate in plates:

        x = int(
            plate["x"]
        )

        y = int(
            plate["y"]
        )

        w = int(
            plate["width"]
        )

        h = int(
            plate["height"]
        )

        if (
            w <= 0
            or h <= 0
        ):
            continue


        # Slight padding around plate
        padding_x = max(
            3,
            int(w * 0.08)
        )

        padding_y = max(
            3,
            int(h * 0.15)
        )


        x1 = max(
            0,
            x - padding_x
        )

        y1 = max(
            0,
            y - padding_y
        )

        x2 = min(
            image_width,
            x + w + padding_x
        )

        y2 = min(
            image_height,
            y + h + padding_y
        )


        region = image[
            y1:y2,
            x1:x2
        ]

        if region.size == 0:
            continue


        region_height, region_width = (
            region.shape[:2]
        )


        kernel_width = max(
            31,
            int(
                region_width * 0.75
            )
        )

        kernel_height = max(
            31,
            int(
                region_height * 0.75
            )
        )


        if kernel_width % 2 == 0:
            kernel_width += 1

        if kernel_height % 2 == 0:
            kernel_height += 1


        blurred = cv2.GaussianBlur(
            region,
            (
                kernel_width,
                kernel_height
            ),
            sigmaX=30,
            sigmaY=30
        )


        # Second pass, same approach
        # we're using for faces.
        blurred = cv2.GaussianBlur(
            blurred,
            (
                kernel_width,
                kernel_height
            ),
            sigmaX=30,
            sigmaY=30
        )


        image[
            y1:y2,
            x1:x2
        ] = blurred

        blurred_count += 1


    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    success = cv2.imwrite(
        str(output_path),
        image
    )


    if not success:
        raise ValueError(
            f"Could not save image: {output_path}"
        )


    return {
        "output_path":
            str(output_path),

        "blurred_count":
            blurred_count,
    }

if __name__ == "__main__":

    input_file = (
        "test_images/plate1.jpg"
    )

    output_file = (
        "output/plate_detected1.jpg"
    )

    result = draw_license_plates(
        input_file,
        output_file
    )

    print(
        "\nPrivChk AI - LICENSE PLATE SCAN"
    )

    print(
        "=" * 50
    )

    print(
        "License plates detected:",
        result["plate_count"]
    )

    for index, plate in enumerate(
        result["plates"],
        start=1
    ):

        print(
            f"\nPlate {index}"
        )

        print(
            "  Confidence:",
            plate["confidence"]
        )

        print(
            "  Position:",
            f"x={plate['x']}, "
            f"y={plate['y']}"
        )

        print(
            "  Size:",
            f"{plate['width']} × "
            f"{plate['height']}"
        )

    print(
        "\nAnnotated image:",
        output_file
    )