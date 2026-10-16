from pathlib import Path

import cv2

SHARPNESS_EDGE = 1024


def sharpness(path: Path) -> float:
    """Variance of the Laplacian on the grayscale image, long edge capped at 1024 px."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"cannot read image: {path}")
    scale = SHARPNESS_EDGE / max(img.shape)
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(img, cv2.CV_64F).var())
