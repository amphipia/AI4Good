from pathlib import Path

import cv2
import numpy as np

def detect_qr_at_scale(
    image,
    scale
):
    """
    Try QR detection at a particular image scale.
    Return results mapped back to original coordinates.
    """

    if scale == 1.0:
        scaled = image
    else:
        scaled = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC
        )

    detector = cv2.QRCodeDetector()

    qr_results = []

    try:

        success, decoded_info, points, _ = (
            detector.detectAndDecodeMulti(
                scaled
            )
        )

    except Exception:

        success = False
        decoded_info = []
        points = None


    if success and points is not None:

        for index, qr_points in enumerate(
            points
        ):

            converted_points = []

            for point in qr_points:

                converted_points.append({
                    "x": int(
                        point[0] / scale
                    ),
                    "y": int(
                        point[1] / scale
                    ),
                })

            decoded_value = ""

            if index < len(
                decoded_info
            ):
                decoded_value = (
                    decoded_info[index]
                    or ""
                )

            qr_results.append({
                "decoded":
                    decoded_value,

                "points":
                    converted_points,
            })

    return qr_results
    
def detect_qr_codes(
    image_path
):
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

    # Normal image first.
    qr_results = detect_qr_at_scale(
        image,
        1.0
    )

    # If nothing found, enlarge and retry.
    if not qr_results:

        qr_results = detect_qr_at_scale(
            image,
            2.0
        )

    if not qr_results:

        qr_results = detect_qr_at_scale(
            image,
            3.0
        )

    return {
        "qr_count":
            len(qr_results),

        "qr_codes":
            qr_results,
    }


def draw_qr_codes(
    input_path,
    output_path
):
    """
    Draw QR outlines for testing/development.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    image = cv2.imread(str(input_path))

    if image is None:
        raise ValueError(
            f"Could not read image: {input_path}"
        )

    result = detect_qr_codes(
        input_path
    )

    for index, qr in enumerate(
        result["qr_codes"],
        start=1
    ):

        points = np.array(
            [
                [
                    point["x"],
                    point["y"],
                ]
                for point in qr["points"]
            ],
            dtype=np.int32
        )

        points = points.reshape(
            (-1, 1, 2)
        )

        cv2.polylines(
            image,
            [points],
            True,
            (0, 255, 0),
            3,
        )

        x = int(
            qr["points"][0]["x"]
        )

        y = int(
            qr["points"][0]["y"]
        )

        label = f"QR {index}"

        cv2.putText(
            image,
            label,
            (
                x,
                max(25, y - 10)
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    cv2.imwrite(
        str(output_path),
        image
    )

    return result

def blur_selected_qr_codes(
    input_path,
    output_path,
    qr_codes,
):
    """
    Blur selected QR regions.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

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

    for qr in qr_codes:

        points = qr.get(
            "points",
            []
        )

        if len(points) < 4:
            continue

        xs = [
            int(point["x"])
            for point in points
        ]

        ys = [
            int(point["y"])
            for point in points
        ]

        x1 = max(
            0,
            min(xs)
        )

        y1 = max(
            0,
            min(ys)
        )

        x2 = min(
            image_width,
            max(xs)
        )

        y2 = min(
            image_height,
            max(ys)
        )

        width = x2 - x1
        height = y2 - y1

        if width <= 0 or height <= 0:
            continue

        # Padding around QR code
        padding_x = int(
            width * 0.10
        )

        padding_y = int(
            height * 0.10
        )

        x1 = max(
            0,
            x1 - padding_x
        )

        y1 = max(
            0,
            y1 - padding_y
        )

        x2 = min(
            image_width,
            x2 + padding_x
        )

        y2 = min(
            image_height,
            y2 + padding_y
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
            61,
            int(region_width * 0.75)
        )

        kernel_height = max(
            61,
            int(region_height * 0.75)
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
        "output_path": str(output_path),
        "blurred_count": blurred_count,
    }

if __name__ == "__main__":

    input_file = (
        "test_images/qr1.jpg"
    )

    output_file = (
        "output/qr_detected1.jpg"
    )

    result = draw_qr_codes(
        input_file,
        output_file
    )

    print("\nPrivChk AI - QR SCAN")
    print("=" * 40)

    print(
        f"QR codes detected: "
        f"{result['qr_count']}"
    )

    for index, qr in enumerate(
        result["qr_codes"],
        start=1
    ):

        print(
            f"\nQR {index}:"
        )

        if qr["decoded"]:

            print(
                f"  Decoded content: "
                f"{qr['decoded']}"
            )

        else:

            print(
                "  Decoded content: "
                "[Detected but could not decode]"
            )

        print(
            "  Points:"
        )

        for point in qr["points"]:

            print(
                f"    "
                f"x={point['x']}, "
                f"y={point['y']}"
            )

    print(
        f"\nAnnotated image saved to:"
        f"\n{output_file}"
    )