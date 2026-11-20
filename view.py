#!/usr/bin/env python3
"""Draw YOLO boxes and named panoptic segment outlines on images.

Single-image example:
    python view.py runs/r23007/delivery/images/000000009448.jpg \
        --classes runs/r23007/delivery/classes.txt \
        --labels runs/r23007/delivery/labels/000000009448.txt \
        --mask runs/r23007/delivery/masks/000000009448.png \
        --panoptic runs/r23007/delivery/panoptic.json

Batch example:
    python view.py --delivery runs/r23007/delivery \
        --out-dir runs/r23007/annotated_images
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BOX_COLORS = (
    (255, 75, 75),
    (70, 220, 110),
    (65, 170, 255),
    (255, 190, 55),
    (220, 90, 255),
    (50, 225, 220),
    (255, 120, 45),
    (160, 235, 65),
)


def read_classes(path: Path) -> dict[int, str]:
    classes: dict[int, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"{path}:{line_number}: expected '<class_id> <name>'")
        try:
            class_id = int(parts[0])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: invalid class id {parts[0]!r}") from exc
        if class_id in classes:
            raise ValueError(f"{path}:{line_number}: duplicate class id {class_id}")
        classes[class_id] = parts[1]
    return classes


def read_boxes(path: Path, classes: dict[int, str]) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            raise ValueError(f"{path}:{line_number}: expected class_id x_center y_center width height")
        try:
            class_id = int(parts[0])
            x_center, y_center, width, height = (float(value) for value in parts[1:5])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: invalid YOLO box") from exc
        if class_id not in classes:
            raise ValueError(f"{path}:{line_number}: class id {class_id} is not defined in classes.txt")
        if not all(math.isfinite(value) for value in (x_center, y_center, width, height)):
            raise ValueError(f"{path}:{line_number}: box coordinates must be finite")
        if width < 0 or height < 0:
            raise ValueError(f"{path}:{line_number}: box width and height must not be negative")
        boxes.append((class_id, x_center, y_center, width, height))
    return boxes


def segment_color(segment_id: int) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb((segment_id * 0.618033988749895) % 1, 0.9, 1.0)
    return round(red * 255), round(green * 255), round(blue * 255)


def draw_segment_outlines(image: Image.Image, mask: Image.Image) -> Image.Image:
    if image.size != mask.size:
        raise ValueError(f"image size {image.size} does not match mask size {mask.size}")

    width, height = mask.size
    pixels = mask.convert("RGB").tobytes()
    overlay = bytearray(width * height * 4)

    for y in range(height):
        for x in range(width):
            pixel_index = y * width + x
            offset = pixel_index * 3
            red, green, blue = pixels[offset : offset + 3]
            segment_id = red | (green << 8) | (blue << 16)
            if segment_id == 0:
                continue

            edge = (
                x == 0
                or x == width - 1
                or y == 0
                or y == height - 1
                or pixels[offset - 3 : offset] != pixels[offset : offset + 3]
                or pixels[offset + 3 : offset + 6] != pixels[offset : offset + 3]
                or pixels[offset - width * 3 : offset - width * 3 + 3] != pixels[offset : offset + 3]
                or pixels[offset + width * 3 : offset + width * 3 + 3] != pixels[offset : offset + 3]
            )
            if edge:
                color_offset = pixel_index * 4
                overlay[color_offset : color_offset + 4] = (*segment_color(segment_id), 230)

    outline = Image.frombytes("RGBA", mask.size, bytes(overlay))
    return Image.alpha_composite(image.convert("RGBA"), outline)


def draw_panoptic_labels(
    image: Image.Image,
    segments_info: list[dict],
    categories: dict[int, dict],
) -> Image.Image:
    result = image.convert("RGB")
    draw = ImageDraw.Draw(result)
    font = ImageFont.load_default()
    width, height = result.size

    for segment in segments_info:
        category = categories.get(segment.get("category_id"))
        bbox = segment.get("bbox")
        if category is None or not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            x, y, _, _ = (float(value) for value in bbox)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(x) or not math.isfinite(y):
            continue

        label = category["name"]
        color = segment_color(int(segment["id"]))
        text_bounds = draw.textbbox((0, 0), label, font=font)
        text_width = text_bounds[2] - text_bounds[0]
        text_height = text_bounds[3] - text_bounds[1]
        left = min(max(round(x), 0), width - 1)
        top = min(max(round(y), 0), height - 1)
        label_top = max(0, top - text_height - 4)
        draw.rectangle(
            (left, label_top, min(width - 1, left + text_width + 6), label_top + text_height + 4),
            fill=color,
        )
        draw.text((left + 3, label_top + 2), label, fill="black", font=font)
    return result


def draw_boxes(
    image: Image.Image,
    boxes: list[tuple[int, float, float, float, float]],
    classes: dict[int, str],
) -> Image.Image:
    result = image.convert("RGB")
    draw = ImageDraw.Draw(result)
    font = ImageFont.load_default()
    width, height = result.size
    line_width = max(2, round(min(width, height) / 320))

    for class_id, x_center, y_center, box_width, box_height in boxes:
        left = round((x_center - box_width / 2) * width)
        top = round((y_center - box_height / 2) * height)
        right = round((x_center + box_width / 2) * width)
        bottom = round((y_center + box_height / 2) * height)
        if right < 0 or bottom < 0 or left >= width or top >= height:
            continue
        left, right = max(0, left), min(width - 1, right)
        top, bottom = max(0, top), min(height - 1, bottom)
        color = BOX_COLORS[class_id % len(BOX_COLORS)]
        draw.rectangle((left, top, right, bottom), outline=color, width=line_width)

        label = classes[class_id]
        text_bounds = draw.textbbox((0, 0), label, font=font)
        text_width = text_bounds[2] - text_bounds[0]
        text_height = text_bounds[3] - text_bounds[1]
        label_top = max(0, top - text_height - 4)
        draw.rectangle(
            (left, label_top, min(width - 1, left + text_width + 6), label_top + text_height + 4),
            fill=color,
        )
        draw.text((left + 3, label_top + 2), label, fill="black", font=font)
    return result


def read_panoptic(path: Path) -> tuple[dict[str, dict], dict[int, dict]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    categories = {int(category["id"]): category for category in document["categories"]}
    images = {
        Path(image["file_name"]).stem: image
        for image in document["images"]
    }
    annotations = {annotation["image_id"]: annotation for annotation in document["annotations"]}
    by_stem = {}
    for stem, image in images.items():
        annotation = annotations.get(image["id"])
        if annotation is not None:
            by_stem[stem] = {
                "mask": Path(annotation["file_name"]),
                "segments_info": annotation["segments_info"],
            }
    return by_stem, categories


def annotate_delivery(delivery: Path, out_dir: Path) -> int:
    classes = read_classes(delivery / "classes.txt")
    panoptic_by_stem, categories = read_panoptic(delivery / "panoptic.json")
    image_dir = delivery / "images"
    label_dir = delivery / "labels"
    mask_dir = delivery / "masks"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for image_path in sorted(path for path in image_dir.iterdir() if path.is_file()):
        stem = image_path.stem
        label_path = label_dir / f"{stem}.txt"
        panoptic = panoptic_by_stem.get(stem)
        if not label_path.is_file() or panoptic is None:
            continue

        mask_path = mask_dir / panoptic["mask"].name
        if not mask_path.is_file():
            continue
        boxes = read_boxes(label_path, classes)
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        with Image.open(mask_path) as source_mask:
            mask = source_mask.convert("RGB")
        if image.size != mask.size:
            raise ValueError(f"{image_path}: image and mask dimensions do not match")

        result = draw_segment_outlines(image, mask)
        result = draw_panoptic_labels(result, panoptic["segments_info"], categories)
        result = draw_boxes(result, boxes, classes)
        result.save(out_dir / image_path.name)
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Vẽ nhãn YOLO và panoptic lên ảnh")
    parser.add_argument("image", nargs="?", help="ảnh đầu vào cho chế độ một ảnh")
    parser.add_argument("--delivery", type=Path, help="delivery cần annotate toàn bộ ảnh")
    parser.add_argument("--classes", help="đường dẫn classes.txt")
    parser.add_argument("--labels", "--label", dest="labels", help="file label YOLO")
    parser.add_argument("--mask", help="file mask panoptic PNG")
    parser.add_argument("--panoptic", help="đường dẫn panoptic.json")
    parser.add_argument("--out", help="ảnh đầu ra chế độ một ảnh")
    parser.add_argument("--out-dir", type=Path, help="thư mục đầu ra chế độ batch")
    args = parser.parse_args()

    if args.delivery:
        if args.image or args.classes or args.labels or args.mask or args.panoptic or args.out:
            parser.error("--delivery chỉ dùng với --out-dir")
        try:
            count = annotate_delivery(
                args.delivery, args.out_dir or args.delivery.parent / "annotated_images",
            )
        except (OSError, ValueError, KeyError) as exc:
            parser.error(str(exc))
        print(f"Đã ghi {count} ảnh annotate")
        return 0

    if not args.image or not args.classes or not args.labels or not args.mask or not args.panoptic:
        parser.error("chế độ một ảnh cần image, --classes, --labels, --mask và --panoptic")

    image_path = Path(args.image)
    classes_path = Path(args.classes)
    labels_path = Path(args.labels)
    mask_path = Path(args.mask)
    panoptic_path = Path(args.panoptic)
    out_path = Path(args.out) if args.out else image_path.with_name(f"{image_path.stem}_view.png")

    try:
        input_paths = (image_path, classes_path, labels_path, mask_path, panoptic_path)
        if out_path.resolve() in {path.resolve() for path in input_paths}:
            parser.error("file đầu ra không được trùng với file đầu vào")
        classes = read_classes(classes_path)
        boxes = read_boxes(labels_path, classes)
        panoptic_by_stem, categories = read_panoptic(panoptic_path)
        annotation = panoptic_by_stem.get(image_path.stem)
        if annotation is None:
            raise ValueError(f"{panoptic_path}: no annotation for {image_path.stem}")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        with Image.open(mask_path) as source_mask:
            mask = source_mask.convert("RGB")
        result = draw_segment_outlines(image, mask)
        result = draw_panoptic_labels(result, annotation["segments_info"], categories)
        result = draw_boxes(result, boxes, classes)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(out_path)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Đã lưu ảnh đã vẽ: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
