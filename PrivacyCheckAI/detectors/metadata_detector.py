from pathlib import Path

from PIL import Image, ImageOps, ExifTags


def dms_to_decimal(dms, ref):
    """
    Convert GPS coordinates from degrees/minutes/seconds
    to decimal latitude/longitude.
    """

    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])

    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

    if ref in ("S", "W"):
        decimal = -decimal

    return decimal


def get_gps_data(exif):
    """
    Extract GPS metadata from Pillow EXIF data.
    """

    gps_data = {}

    try:
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        return gps_data

    for tag_id, value in gps_ifd.items():
        tag_name = ExifTags.GPSTAGS.get(tag_id, str(tag_id))
        gps_data[tag_name] = value

    return gps_data


def get_general_exif(exif):
    """
    Extract readable top-level EXIF fields.
    """

    metadata = {}

    for tag_id, value in exif.items():

        # GPS gets processed separately
        if tag_id == ExifTags.IFD.GPSInfo:
            continue

        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))

        # Ignore nested EXIF pointer
        if tag_name != "ExifOffset":
            metadata[tag_name] = value

    # Some important metadata such as DateTimeOriginal
    # lives inside the EXIF sub-IFD.
    try:
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)

        for tag_id, value in exif_ifd.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            metadata[tag_name] = value

    except Exception:
        pass

    return metadata


def scan_metadata(image_path):
    """
    Scan an image and return privacy-relevant metadata.
    """

    image_path = Path(image_path)

    result = {
        "file": str(image_path),
        "has_exif": False,
        "has_gps": False,
        "latitude": None,
        "longitude": None,
        "camera_make": None,
        "camera_model": None,
        "datetime": None,
        "software": None,
        "all_metadata": {},
    }

    with Image.open(image_path) as image:

        # Needed for formats where metadata may be loaded lazily
        image.load()

        exif = image.getexif()

        if not exif:
            return result

        result["has_exif"] = True

        metadata = get_general_exif(exif)
        result["all_metadata"] = metadata

        result["camera_make"] = metadata.get("Make")
        result["camera_model"] = metadata.get("Model")

        # Prefer original capture time if available
        result["datetime"] = (
            metadata.get("DateTimeOriginal")
            or metadata.get("DateTimeDigitized")
            or metadata.get("DateTime")
        )

        result["software"] = metadata.get("Software")

        gps = get_gps_data(exif)

        latitude = gps.get("GPSLatitude")
        latitude_ref = gps.get("GPSLatitudeRef")

        longitude = gps.get("GPSLongitude")
        longitude_ref = gps.get("GPSLongitudeRef")

        if (
            latitude
            and latitude_ref
            and longitude
            and longitude_ref
        ):
            result["latitude"] = dms_to_decimal(
                latitude,
                latitude_ref
            )

            result["longitude"] = dms_to_decimal(
                longitude,
                longitude_ref
            )

            result["has_gps"] = True

    return result


def create_safe_copy(input_path, output_path):
    """
    Create a copy of the image without EXIF metadata.
    The original image is never modified.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with Image.open(input_path) as image:

        image.load()

        # Apply EXIF orientation before removing EXIF.
        clean_image = ImageOps.exif_transpose(image)

        # Make a pixel copy and remove inherited metadata.
        clean_image = clean_image.copy()
        clean_image.info.clear()

        suffix = output_path.suffix.lower()

        if suffix in (".jpg", ".jpeg"):

            # JPEG cannot save RGBA directly.
            if clean_image.mode not in ("RGB", "L"):
                clean_image = clean_image.convert("RGB")

            clean_image.save(
                output_path,
                format="JPEG",
                quality=95
            )

        elif suffix == ".png":

            clean_image.save(
                output_path,
                format="PNG"
            )

        else:
            # For the MVP, output unknown formats as PNG.
            output_path = output_path.with_suffix(".png")

            clean_image.save(
                output_path,
                format="PNG"
            )

    return output_path


def print_report(result):
    """
    Print a user-friendly PrivChk privacy report.
    """

    print("\n" + "=" * 50)
    print("PrivChk AI - METADATA SCAN")
    print("=" * 50)

    print(f"\nFile: {result['file']}")

    if not result["has_exif"]:
        print("\n No EXIF metadata detected.")
        return

    print("\nEXIF metadata detected.")

    if result["camera_make"]:
        print(
            f"Camera manufacturer: "
            f"{result['camera_make']}"
        )

    if result["camera_model"]:
        print(
            f"Camera/device model: "
            f"{result['camera_model']}"
        )

    if result["datetime"]:
        print(
            f"Date/time: "
            f"{result['datetime']}"
        )

    if result["software"]:
        print(
            f"Software: "
            f"{result['software']}"
        )

    if result["has_gps"]:

        print("\n⚠ GPS LOCATION FOUND")

        print(
            f"Latitude:  "
            f"{result['latitude']:.6f}"
        )

        print(
            f"Longitude: "
            f"{result['longitude']:.6f}"
        )

        print(
            "\nPrivacy risk: HIGH\n"
            "This image contains coordinates that may reveal "
            "where the photo was taken."
        )

    else:

        print("\n No GPS coordinates detected.")

    print("\nPrivacy-relevant metadata:")

    display_metadata = get_display_metadata(
        result["all_metadata"]
    )

    for name, value in display_metadata.items():
        print(f"  {name}: {value}")

def decode_user_comment(value):
    """
    Attempt to decode an EXIF UserComment into readable text.
    Returns None when the content is mostly binary/unreadable.
    """

    if not isinstance(value, (bytes, bytearray)):
        return str(value)

    try:
        # EXIF UserComment can start with an 8-byte encoding identifier:
        # ASCII\0\0\0
        # UNICODE\0
        # JIS\0\0\0\0\0
        if value.startswith(b"ASCII\x00\x00\x00"):
            raw = value[8:]
            text = raw.decode("ascii", errors="ignore").strip("\x00").strip()

        elif value.startswith(b"UNICODE\x00"):
            raw = value[8:]

            # UTF-16 is commonly used for EXIF Unicode comments.
            try:
                text = raw.decode("utf-16", errors="ignore")
            except Exception:
                return None

            text = text.strip("\x00").strip()

        else:
            text = value.decode("utf-8", errors="ignore").strip("\x00").strip()

        if not text:
            return None

        # Check whether most characters are actually printable.
        printable = sum(
            1 for char in text
            if char.isprintable()
        )

        ratio = printable / len(text)

        if ratio < 0.85:
            return None

        # Avoid dumping enormous metadata blocks into UI.
        if len(text) > 250:
            text = text[:250] + "..."

        return text

    except Exception:
        return None

def get_display_metadata(metadata):
    """
    Convert raw EXIF metadata into clean, user-friendly fields.
    """

    display = {}

    friendly_names = {
        "Make": "Device manufacturer",
        "Model": "Device model",
        "DateTime": "Date/time",
        "DateTimeOriginal": "Original date/time",
        "Software": "Software",
        "Artist": "Author/artist",
        "Copyright": "Copyright",
        "ImageDescription": "Image description",
    }

    for key, friendly_name in friendly_names.items():
        value = metadata.get(key)

        if value is not None:
            display[friendly_name] = str(value)

    # Handle UserComment separately
    user_comment = metadata.get("UserComment")

    if user_comment is not None:

        decoded = decode_user_comment(user_comment)

        if decoded:
            display["Embedded comment"] = decoded
        else:
            display["Embedded comment"] = "Present"

    # Never display raw MakerNote bytes
    if metadata.get("MakerNote") is not None:
        display["Manufacturer-specific metadata"] = "Present"

    return display
    
if __name__ == "__main__":

    input_file = "test_images/photo.jpg"

    safe_file = "output/photo_safe.jpg"

    # STEP 1: Scan original
    original_result = scan_metadata(input_file)

    print_report(original_result)

    # STEP 2: Remove metadata
    created_file = create_safe_copy(
        input_file,
        safe_file
    )

    print(
        f"\n Safe copy created:\n{created_file}"
    )

    # STEP 3: Verify metadata has been removed
    safe_result = scan_metadata(created_file)

    print("\nVERIFYING SAFE COPY...")

    print_report(safe_result)