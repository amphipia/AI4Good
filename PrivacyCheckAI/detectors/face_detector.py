from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "face_detection_yunet_2026may.onnx"
)

CONFIDENCE_THRESHOLD = 0.60
NMS_THRESHOLD = 0.3
TOP_K = 5000

def apply_feathered_blur(
    image,
    x1,
    y1,
    x2,
    y2,
    use_ellipse=False,
):
    """
    Blur a region and blend it back with a soft mask
    so the result looks more natural.
    """

    roi = image[y1:y2, x1:x2]

    if roi.size == 0:
        return

    roi_h, roi_w = roi.shape[:2]

    # Strong blur
    kernel_w = max(61, int(roi_w * 0.75))
    kernel_h = max(61, int(roi_h * 0.75))

    if kernel_w % 2 == 0:
        kernel_w += 1

    if kernel_h % 2 == 0:
        kernel_h += 1

    blurred = cv2.GaussianBlur(
        roi,
        (kernel_w, kernel_h),
        sigmaX=30,
        sigmaY=30
    )

    blurred = cv2.GaussianBlur(
        blurred,
        (kernel_w, kernel_h),
        sigmaX=30,
        sigmaY=30
    )

    # -----------------------------------------
    # Build mask
    # -----------------------------------------
    mask = np.zeros(
        (roi_h, roi_w),
        dtype=np.uint8
    )

    if use_ellipse:
        cv2.ellipse(
            mask,
            (
                roi_w // 2,
                roi_h // 2
            ),
            (
                max(1, int(roi_w * 0.45)),
                max(1, int(roi_h * 0.48))
            ),
            0,
            0,
            360,
            255,
            -1
        )
    else:
        cv2.rectangle(
            mask,
            (0, 0),
            (roi_w, roi_h),
            255,
            -1
        )

    # Feather mask edges
    feather = max(
        15,
        int(min(roi_w, roi_h) * 0.12)
    )

    if feather % 2 == 0:
        feather += 1

    mask = cv2.GaussianBlur(
        mask,
        (feather, feather),
        0
    )

    alpha = mask.astype("float32") / 255.0
    alpha = np.dstack([alpha, alpha, alpha])

    blended = (
        blurred.astype("float32") * alpha
        + roi.astype("float32") * (1 - alpha)
    )

    image[y1:y2, x1:x2] = blended.astype(
        "uint8"
    )
    
def create_detector(image_width, image_height):
    """
    Create the OpenCV YuNet face detector.
    """

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Face detector model not found: {MODEL_PATH}"
        )

    detector = cv2.FaceDetectorYN.create(
        str(MODEL_PATH),
        "",
        (image_width, image_height),
        CONFIDENCE_THRESHOLD,
        NMS_THRESHOLD,
        TOP_K,
    )

    return detector


def detect_faces(image_path):
    """
    Detect faces in an image.

    Returns:
        {
            "face_count": int,
            "faces": [
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

    image_path = Path(image_path)

    image = cv2.imread(str(image_path))

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    height, width = image.shape[:2]

    detector = create_detector(
        width,
        height
    )

    _, faces = detector.detect(image)

    results = []

    if faces is not None:

        for face in faces:

            # YuNet output:
            # x, y, width, height,
            # 5 facial landmark pairs,
            # confidence
            x = int(face[0])
            y = int(face[1])
            w = int(face[2])
            h = int(face[3])

            confidence = float(face[-1])

            results.append({
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "confidence": round(
                    confidence,
                    4
                ),
            })

    return {
        "face_count": len(results),
        "faces": results,
    }

def blur_faces(
    input_path,
    output_path,
):
    input_path = Path(input_path)
    output_path = Path(output_path)

    image = cv2.imread(str(input_path))

    if image is None:
        raise ValueError(
            f"Could not read image: {input_path}"
        )

    result = detect_faces(input_path)

    image_height, image_width = image.shape[:2]

    for face in result["faces"]:

        x = face["x"]
        y = face["y"]
        w = face["width"]
        h = face["height"]

        # Extend beyond the detector's exact face box.
        padding_x = int(w * 0.22)
        padding_y = int(h * 0.25)
        #padding_x = 0
        #padding_y = 0

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

        face_region = image[
            y1:y2,
            x1:x2
        ]

        if face_region.size == 0:
            continue

        region_height, region_width = face_region.shape[:2]

        # Strong blur kernel based on face size
        kernel_width = max(
            61,
            int(region_width * 0.75)
        )

        kernel_height = max(
            61,
            int(region_height * 0.75)
        )

        # GaussianBlur requires odd kernel sizes
        if kernel_width % 2 == 0:
            kernel_width += 1

        if kernel_height % 2 == 0:
            kernel_height += 1

        blurred_face = cv2.GaussianBlur(
            face_region,
            (
                kernel_width,
                kernel_height
            ),
            sigmaX=30,
            sigmaY=30
        )

        # Apply a second pass for stronger anonymization
        blurred_face = cv2.GaussianBlur(
            blurred_face,
            (
                kernel_width,
                kernel_height
            ),
            sigmaX=30,
            sigmaY=30
        )

        # Put the blurred region back
        #image[y1:y2, x1:x2] = blurred_face
        apply_feathered_blur(
            image,
            x1,
            y1,
            x2,
            y2,
            use_ellipse=True
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

    return {
        "output_path": str(output_path),
        "face_count": result["face_count"],
        "faces": result["faces"],
    }

def draw_faces(
    input_path,
    output_path
):
    """
    Create a copy of the image with boxes drawn
    around detected faces.

    Useful for development/testing only.
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

    result = detect_faces(
        input_path
    )

    for index, face in enumerate(
        result["faces"],
        start=1
    ):

        x = face["x"]
        y = face["y"]
        w = face["width"]
        h = face["height"]

        confidence = face[
            "confidence"
        ]

        cv2.rectangle(
            image,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2,
        )

        cv2.putText(
            image,
            f"Face {index}: {confidence:.2f}",
            (x, max(20, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
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

def blur_selected_faces(
    input_path,
    output_path,
    faces,
):
    """
    Blur only the face bounding boxes supplied by the client.

    faces should contain objects like:
    {
        "x": 100,
        "y": 80,
        "width": 150,
        "height": 170
    }
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    image = cv2.imread(str(input_path))

    if image is None:
        raise ValueError(
            f"Could not read image: {input_path}"
        )

    image_height, image_width = image.shape[:2]

    blurred_count = 0

    for face in faces:

        x = int(face["x"])
        y = int(face["y"])
        w = int(face["width"])
        h = int(face["height"])

        # 20% padding around detected face
        padding_x = int(w * 0.22)
        padding_y = int(h * 0.25)

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

        face_region = image[
            y1:y2,
            x1:x2
        ]

        if face_region.size == 0:
            continue

        region_height, region_width = (
            face_region.shape[:2]
        )

        kernel_width = max(
            61,
            int(region_width * 0.75)
        )

        kernel_height = max(
            61,
            int(region_height * 0.75)
        )

        # GaussianBlur requires odd kernel sizes
        if kernel_width % 2 == 0:
            kernel_width += 1

        if kernel_height % 2 == 0:
            kernel_height += 1

        blurred_face = cv2.GaussianBlur(
            face_region,
            (
                kernel_width,
                kernel_height
            ),
            sigmaX=30,
            sigmaY=30
        )

        # Second pass
        blurred_face = cv2.GaussianBlur(
            blurred_face,
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
        ] = blurred_face

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
        "test_images/faces.jpg"
    )

    output_file = (
        "output/faces_detected.jpg"
    )

    result = draw_faces(
        input_file,
        output_file
    )

    print("\nPrivChk AI - FACE SCAN")
    print("=" * 40)

    print(
        f"Faces detected: "
        f"{result['face_count']}"
    )

    for index, face in enumerate(
        result["faces"],
        start=1
    ):
        print(
            f"\nFace {index}:"
        )

        print(
            f"  Confidence: "
            f"{face['confidence']}"
        )

        print(
            f"  Position: "
            f"x={face['x']}, "
            f"y={face['y']}"
        )

        print(
            f"  Size: "
            f"{face['width']} x "
            f"{face['height']}"
        )

    print(
        f"\nAnnotated image saved to:"
        f"\n{output_file}"
    )