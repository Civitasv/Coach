"""Strict local-only icon template classification; abstain on uncertainty.

Templates must be explicitly added by the player. Not a detector: caller must
supply a calibrated single-icon crop from a named ROI.
"""
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageChops, ImageStat


@dataclass(frozen=True)
class IconResult:
    name: str | None
    confidence: float
    source: str = 'local_template'


class IconMatcher:
    def __init__(self, templates, min_score=.91, min_margin=.06):
        self.templates = {str(name): self.normalize(im) for name,im in templates.items()}
        self.min_score = min_score
        self.min_margin = min_margin

    @classmethod
    def from_directory(cls, directory):
        directory = Path(directory)
        templates = {}
        if directory.exists():
            for path in sorted(directory.glob('*.png')):
                try:
                    with Image.open(path) as image:
                        templates[path.stem] = image.convert('RGB').copy()
                except (OSError, ValueError):
                    continue
        return cls(templates)

    @staticmethod
    def normalize(image):
        return image.convert('L').resize((48,48), Image.Resampling.BILINEAR)

    def classify(self, crop):
        if not self.templates:
            return IconResult(None, 0)
        query = self.normalize(crop)
        if ImageStat.Stat(query).stddev[0] < 12:
            return IconResult(None, 0)
        scores = []
        for name, template in self.templates.items():
            error = ImageStat.Stat(ImageChops.difference(query,template)).mean[0]
            scores.append((max(0., 1 - error/255.),name))
        scores.sort(reverse=True)
        score,name = scores[0]
        runner_up = scores[1][0] if len(scores)>1 else 0.
        if score < self.min_score or score-runner_up < self.min_margin:
            return IconResult(None,score)
        return IconResult(name,score)