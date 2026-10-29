"""Optional local Chinese OCR, initialized lazily in a background worker.

Pure-Python adapters can be tested without installing inference dependencies.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float
    box: tuple = ()


def lines_from_result(result) -> list[OCRLine]:
    """RapidOCR 3.x results have aligned txts / scores / boxes arrays."""
    texts = getattr(result, 'txts', None) or []
    scores = getattr(result, 'scores', None)
    boxes = getattr(result, 'boxes', None)
    output = []
    for idx, value in enumerate(texts):
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            score = float(scores[idx]) if scores is not None else 0.0
        except (ValueError, TypeError, IndexError):
            score = 0.0
        if not 0 <= score <= 1:
            score = 0.0
        try:
            box = tuple(tuple(map(int, p)) for p in boxes[idx]) if boxes is not None else ()
        except (ValueError, TypeError, IndexError):
            box = ()
        output.append(OCRLine(value.strip(), score, box))
    return output


def trusted_text(lines: Iterable[OCRLine], min_confidence=0.75, limit=45):
    return '\n'.join(line.text for line in list(lines)[:limit]
                     if line.confidence >= min_confidence)


class LocalOCR:
    def __init__(self):
        try:
            from rapidocr import RapidOCR
        except ImportError as exc:
            raise RuntimeError('未安装本地 OCR：请运行 pip install -r requirements.txt') from exc
        self.engine = RapidOCR()

    def recognize(self, image):
        # RapidOCR accepts Pillow Images directly; scale down overlarge desktop crops
        # to reduce CPU use. No screenshots are transmitted over the network here.
        image = image.copy().convert('RGB')
        if image.width > 1600 or image.height > 1100:
            image.thumbnail((1600, 1100))
        return lines_from_result(self.engine(image))