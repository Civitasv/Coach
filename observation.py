"""Pure, local structured observation: normalized ROIs and provenance-aware facts.

This module has no screen capture, network or Tk dependency.
"""
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path

ROI_NAMES = frozenset(('health', 'energy', 'round', 'shop', 'pool', 'enemy_board',
                       'weapon', 'enemy_icon', *(f'shop_slot_{i}' for i in range(1, 6))))


@dataclass(frozen=True)
class ROI:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        values = (self.x, self.y, self.width, self.height)
        if (not all(isinstance(v, (float, int)) and not isinstance(v, bool)
                    and math.isfinite(v) for v in values)
                or self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0
                or self.x + self.width > 1.00000001 or self.y + self.height > 1.00000001):
            raise ValueError('ROI must be a non-empty normalized rectangle within the game area')

    def pixels(self, width: int, height: int):
        if width <= 0 or height <= 0:
            raise ValueError('Image dimensions must be positive')
        x1, y1 = round(self.x * width), round(self.y * height)
        x2, y2 = round((self.x + self.width) * width), round((self.y + self.height) * height)
        if x2 <= x1 or y2 <= y1:
            raise ValueError('ROI is too small for this resolution')
        return (x1, y1, min(width, x2), min(height, y2))


@dataclass(eq=True)
class Calibration:
    regions: dict[str, ROI] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self):
        if self.version != 1 or not all(k in ROI_NAMES and isinstance(v, ROI)
                                        for k, v in self.regions.items()):
            raise ValueError('Unsupported calibration format or unknown ROI name')

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if set(data) != {'version', 'regions'} or not isinstance(data['regions'], dict):
            raise ValueError('Invalid calibration document')
        return cls({name: ROI(**rect) for name, rect in data['regions'].items()}, data['version'])

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.tmp')
        try:
            with temp.open('w', encoding='utf-8') as f:
                json.dump({'version': self.version, 'regions': {k: asdict(v) for k,v in self.regions.items()}},
                          f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def scoped_lines(lines, calibration: Calibration, width: int, height: int):
    """Only geometrically located OCR lines are admitted to specific ROIs."""
    output = {k: [] for k in calibration.regions}
    for line in lines:
        if not line.box:
            continue
        try:
            cx = sum(point[0] for point in line.box) / len(line.box)
            cy = sum(point[1] for point in line.box) / len(line.box)
        except (TypeError, ValueError, IndexError, ZeroDivisionError):
            continue
        for name, roi in calibration.regions.items():
            x1,y1,x2,y2 = roi.pixels(width,height)
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                output[name].append(line)
    return output


@dataclass(frozen=True)
class Observation:
    field: str
    value: str
    confidence: float
    source: str
    observed_at: float
    expires_at: float

    def __post_init__(self):
        if (not self.field or not self.source or not isinstance(self.value, str)
                or not 0 <= self.confidence <= 1 or self.expires_at <= self.observed_at):
            raise ValueError('Invalid observation')


@dataclass
class FactLedger:
    facts: dict[str, Observation] = field(default_factory=dict)
    conflicts: dict[str, tuple] = field(default_factory=dict)
    minimum_confidence: float = 0.82

    def accept(self, field, observation):
        if field != observation.field or observation.confidence < self.minimum_confidence:
            return False
        old = self.facts.get(field)
        if old and old.observed_at > observation.observed_at:
            return False
        if (old and old.source == 'manual' and observation.source != 'manual'
                and old.expires_at >= observation.observed_at):
            return False
        if (field in self.conflicts and observation.source != 'manual'
                and self.conflicts[field][0] == observation.observed_at):
            return False
        if (old and old.observed_at == observation.observed_at
                and old.value != observation.value and observation.source != 'manual'):
            self.facts.pop(field, None)
            self.conflicts[field] = (observation.observed_at, old.value, observation.value)
            return False
        self.facts[field] = observation
        self.conflicts.pop(field, None)
        return True

    def get(self, field, now):
        observed = self.facts.get(field)
        return observed if observed and observed.observed_at <= now <= observed.expires_at else None

    def snapshot(self, now):
        return {name: asdict(obs) for name, obs in self.facts.items() if self.get(name, now)}