from pathlib import Path
import re

import cv2
import easyocr
import numpy as np


# Load once, not once per image.
# gpu=False keeps the first version simple and portable.
reader = easyocr.Reader(
    ["en"],
    gpu=False
)


MIN_CONFIDENCE = 0.35


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_PATTERN = re.compile(
    r"""
    (?<!\d)
    (?:\+?1[\s.-]?)?
    \(?\d{3}\)?
    [\s.-]?
    \d{3}
    [\s.-]?
    \d{4}
    (?!\d)
    """,
    re.VERBOSE
)

SSN_PATTERN = re.compile(
    r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b"
)

URL_PATTERN = re.compile(
    r"\b(?:https?://|www\.)\S+",
    re.IGNORECASE
)

ADDRESS_PATTERN = re.compile(
    r"""
    \b
    \d{1,6}
    \s+
    [A-Za-z0-9.' -]+
    \s+
    (?:
        Street|St|
        Avenue|Ave|
        Road|Rd|
        Drive|Dr|
        Lane|Ln|
        Boulevard|Blvd|
        Court|Ct|
        Parkway|Pkwy|
        Place|Pl|
        Terrace|Ter
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE
)

def redact_selected_text(
    input_path,
    output_path,
    text_items,
):
    """
    Redact selected OCR regions using solid black boxes.
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

    redacted_count = 0

    for item in text_items:

        points = item.get(
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

        # Small padding so characters at box edges
        # are not accidentally left visible.
        padding_x = max(
            2,
            int(width * 0.04)
        )

        padding_y = max(
            2,
            int(height * 0.12)
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

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0, 0, 0),
            thickness=-1
        )

        redacted_count += 1

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
        "redacted_count": redacted_count,
    }
    
def draw_label(
    image,
    text,
    x,
    y,
    color
):
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1

    (text_width, text_height), baseline = (
        cv2.getTextSize(
            text,
            font,
            font_scale,
            thickness
        )
    )

    # Prefer putting the label above the box.
    label_y = y - 6

    # If there is not enough space above,
    # put the label just below the top edge.
    if label_y - text_height < 0:
        label_y = y + text_height + 6

    # Background rectangle improves readability.
    cv2.rectangle(
        image,
        (
            x,
            label_y - text_height - 3
        ),
        (
            x + text_width + 6,
            label_y + baseline + 2
        ),
        color,
        -1
    )

    cv2.putText(
        image,
        text,
        (
            x + 3,
            label_y
        ),
        font,
        font_scale,
        (0, 0, 0),
        thickness,
        cv2.LINE_AA
    )
    
def get_bounds(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    return {
        "x1": min(xs),
        "y1": min(ys),
        "x2": max(xs),
        "y2": max(ys),
    }


def merge_same_line_items(raw_items):
    """
    Merge OCR boxes that appear to belong to the same text line.
    """

    prepared = []

    for box, text, confidence in raw_items:

        bounds = get_bounds(box)

        height = bounds["y2"] - bounds["y1"]

        prepared.append({
            "box": box,
            "text": text,
            "confidence": float(confidence),
            "x1": bounds["x1"],
            "y1": bounds["y1"],
            "x2": bounds["x2"],
            "y2": bounds["y2"],
            "height": height,
            "center_y": (
                bounds["y1"] + bounds["y2"]
            ) / 2,
        })

    # Sort top-to-bottom, then left-to-right
    prepared.sort(
        key=lambda item: (
            item["center_y"],
            item["x1"]
        )
    )

    lines = []

    for item in prepared:

        matched_line = None

        for line in lines:

            average_height = max(
                1,
                (
                    line["height"]
                    + item["height"]
                ) / 2
            )

            y_difference = abs(
                line["center_y"]
                - item["center_y"]
            )

            # Same approximate horizontal line
            if y_difference <= average_height * 0.6:

                matched_line = line
                break

        if matched_line is None:

            lines.append({
                "items": [item],
                "center_y": item["center_y"],
                "height": item["height"],
            })

        else:

            matched_line["items"].append(
                item
            )

            matched_line["center_y"] = (
                sum(
                    i["center_y"]
                    for i
                    in matched_line["items"]
                )
                / len(
                    matched_line["items"]
                )
            )

    merged = []

    for line in lines:

        items = sorted(
            line["items"],
            key=lambda item: item["x1"]
        )

        # Merge nearby items on the same line.
        groups = []
        current_group = []

        for item in items:

            if not current_group:

                current_group.append(item)
                continue

            previous = current_group[-1]

            horizontal_gap = (
                item["x1"]
                - previous["x2"]
            )

            average_height = max(
                1,
                (
                    item["height"]
                    + previous["height"]
                ) / 2
            )

            # Allow slightly larger gaps between OCR fragments
            if horizontal_gap <= average_height * 1.5:

                current_group.append(item)

            else:

                groups.append(
                    current_group
                )

                current_group = [item]

        if current_group:
            groups.append(
                current_group
            )

        for group in groups:

            # Join without a space when fragments clearly
            # look like parts of email/URL punctuation.
            combined_text = group[0]["text"]

            for item in group[1:]:

                next_text = item["text"]

                if (
                    next_text.startswith(
                        (
                            ".",
                            ",",
                            "@",
                            "/",
                            ":"
                        )
                    )
                    or combined_text.endswith(
                        (
                            "@",
                            "/",
                            ":"
                        )
                    )
                ):
                    combined_text += next_text

                else:
                    combined_text += (
                        " " + next_text
                    )

            x1 = min(
                item["x1"]
                for item in group
            )

            y1 = min(
                item["y1"]
                for item in group
            )

            x2 = max(
                item["x2"]
                for item in group
            )

            y2 = max(
                item["y2"]
                for item in group
            )

            confidence = sum(
                item["confidence"]
                for item in group
            ) / len(group)

            merged.append({
                "text": combined_text,
                "confidence": confidence,
                "points": [
                    {"x": int(x1), "y": int(y1)},
                    {"x": int(x2), "y": int(y1)},
                    {"x": int(x2), "y": int(y2)},
                    {"x": int(x1), "y": int(y2)},
                ],
            })

    return merged
    
def luhn_valid(number):
    """
    Used to reduce false positives for card-like numbers.
    """

    digits = [
        int(char)
        for char in number
        if char.isdigit()
    ]

    if not 13 <= len(digits) <= 19:
        return False

    checksum = 0
    parity = len(digits) % 2

    for index, digit in enumerate(digits):

        if index % 2 == parity:
            digit *= 2

            if digit > 9:
                digit -= 9

        checksum += digit

    return checksum % 10 == 0


def classify_text(text):
    """
    Return privacy-related classifications for OCR text.
    """

    findings = []

    if EMAIL_PATTERN.search(text):
        findings.append("email_address")

    if PHONE_PATTERN.search(text):
        findings.append("phone_number")

    if SSN_PATTERN.search(text):
        findings.append("ssn_like")

    if URL_PATTERN.search(text):
        findings.append("web_address")

    if ADDRESS_PATTERN.search(text):
        findings.append("street_address")

    # Strip spaces and punctuation before checking
    # whether this resembles a payment-card number.
    possible_card = re.sub(
        r"[^\d]",
        "",
        text
    )

    if (
        13 <= len(possible_card) <= 19
        and luhn_valid(possible_card)
    ):
        findings.append(
            "payment_card_like"
        )

    return findings


def detect_text(image_path):
    """
    OCR an image and identify potentially sensitive text.

    Returns coordinates, OCR text, confidence,
    and basic privacy classifications.
    """

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    '''raw_results = reader.readtext(
        str(image_path)
    )'''
    ocr_image = cv2.imread(
        str(image_path),
        cv2.IMREAD_GRAYSCALE
    )

    if ocr_image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    raw_results = reader.readtext(
        ocr_image
    )
    

    merged_items = merge_same_line_items(
        raw_results
    )

    detected_text = []
    privacy_items = []


    for item in merged_items:

        #print( "MERGED OCR:", repr( item["text"] ) )

        text = item["text"]

        confidence = float(
            item["confidence"]
        )

        if confidence < MIN_CONFIDENCE:
            continue

        classifications = classify_text(
            text
        )

        result_item = {
            "text": text,
            "confidence": round(
                confidence,
                4
            ),
            "points": item["points"],
            "privacy_types":
                classifications,
        }

        detected_text.append(
            result_item
        )

        if classifications:

            privacy_items.append(
                result_item
            )

    return {
        "text_count":
            len(detected_text),

        "privacy_text_count":
            len(privacy_items),

        "text_items":
            detected_text,

        "privacy_items":
            privacy_items,
    }


def draw_text_findings(
    input_path,
    output_path
):
    """
    Draw OCR boxes.

    Yellow = ordinary text
    Red = text matching a privacy pattern.
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

    result = detect_text(
        input_path
    )

    for item in result[
        "text_items"
    ]:

        points = np.array(
            [
                [
                    p["x"],
                    p["y"]
                ]
                for p in item["points"]
            ],
            dtype=np.int32
        )

        points = points.reshape(
            (-1, 1, 2)
        )

        if item["privacy_types"]:

            color = (
                0,
                0,
                255
            )

        else:

            color = (
                0,
                255,
                255
            )

        cv2.polylines(
            image,
            [points],
            True,
            color,
            2
        )

        x = item["points"][0]["x"]
        y = item["points"][0]["y"]

        if item["privacy_types"]:

            label = ",".join(
                item[
                    "privacy_types"
                ]
            )

        else:

            label = ""

        if label:

            draw_label(
                image,
                label,
                x,
                y,
                color
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


if __name__ == "__main__":

    input_file = (
        "test_images/text1.jpg"
    )

    output_file = (
        "output/text_detected1.jpg"
    )

    result = draw_text_findings(
        input_file,
        output_file
    )

    print(
        "\nPrivChk AI - TEXT SCAN"
    )

    print(
        "=" * 50
    )

    print(
        "Text regions detected:",
        result["text_count"]
    )

    print(
        "Potential privacy items:",
        result[
            "privacy_text_count"
        ]
    )

    for index, item in enumerate(
        result["privacy_items"],
        start=1
    ):

        print(
            f"\nPrivacy item {index}"
        )

        print(
            "  Text:",
            item["text"]
        )

        print(
            "  Type:",
            ", ".join(
                item[
                    "privacy_types"
                ]
            )
        )

        print(
            "  Confidence:",
            item["confidence"]
        )

    print(
        "\nAnnotated image:",
        output_file
    )