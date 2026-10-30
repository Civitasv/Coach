"""Local-only high-frequency observer, independent of Qt and model providers.

One producer owns the OCR worker. Frames are kept in a single latest-frame slot,
so a slow UI never builds a backlog of stale screenshots.
"""
import io
import queue
import threading
import time

import mss
from PIL import Image, ImageChops, ImageStat

from icon_matcher import IconMatcher
from local_ocr import LocalOCR
from observation import scoped_lines


def grab(rect):
    with mss.mss() as screen:
        shot = screen.grab(rect)
    return Image.frombytes('RGB', shot.size, shot.rgb)


def jpeg(image):
    shot = image.copy().convert('RGB')
    shot.thumbnail((1920, 1600))
    buf = io.BytesIO()
    shot.save(buf, 'JPEG', quality=85)
    return buf.getvalue()


def changed(image, old):
    thumb = image.convert('L').resize((128, 72))
    if old is None:
        return True, thumb
    return ImageStat.Stat(ImageChops.difference(thumb, old)).mean[0] >= 2.3, thumb


class Observer:
    def __init__(self, run_id, rect, calibration, templates_dir,
                 sample_interval=.5, ocr_interval=1.5, ocr_factory=LocalOCR,
                 capture=grab):
        self.run_id = run_id
        self.rect = dict(rect)
        self.calibration = calibration
        self.templates_dir = templates_dir
        self.sample_interval = max(.3, float(sample_interval))
        self.ocr_interval = max(.6, float(ocr_interval))
        self.ocr_factory = ocr_factory
        self.capture = capture
        self.stop_event = threading.Event()
        self.events = queue.Queue(maxsize=4)
        self._frame_lock = threading.Lock()
        self._frame = None
        self._frame_seq = 0
        self.thread = None

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Observer can only start once')
        self.thread = threading.Thread(target=self._run, daemon=True, name='CoachOCR')
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def latest(self, seen=0):
        with self._frame_lock:
            if self._frame_seq <= seen:
                return seen, None
            return self._frame_seq, self._frame

    def _event(self, kind, payload):
        try:
            self.events.put_nowait((kind, payload))
        except queue.Full:
            # Prefer dropping stale OCR events over blocking the capture thread.
            try:
                self.events.get_nowait()
            except queue.Empty:
                pass
            self.events.put_nowait((kind, payload))

    def _run(self):
        try:
            ocr = self.ocr_factory()
            matcher = IconMatcher.from_directory(self.templates_dir)
            previous = None
            next_ocr = refresh_at = 0.0
            while not self.stop_event.is_set():
                started = time.monotonic()
                image = self.capture(self.rect)
                different, previous = changed(image, previous)
                with self._frame_lock:
                    self._frame = image
                    self._frame_seq += 1
                if started >= next_ocr and (different or started >= refresh_at):
                    lines = ocr.recognize(image)
                    scoped = scoped_lines(lines, self.calibration, *image.size) if self.calibration.regions else None
                    if scoped is not None:
                        for name in ('health', 'energy', 'round', 'weapon'):
                            scoped.setdefault(name, lines)
                    icons = {}
                    for name, roi in self.calibration.regions.items():
                        if name.startswith('shop_slot_') or name == 'enemy_icon':
                            try:
                                icons[name] = matcher.classify(image.crop(roi.pixels(*image.size)))
                            except ValueError:
                                pass
                    self._event('ocr', (lines, scoped, icons))
                    next_ocr = time.monotonic() + self.ocr_interval
                    refresh_at = time.monotonic() + 8.
                self.stop_event.wait(max(0., self.sample_interval - (time.monotonic() - started)))
        except Exception as exc:
            self._event('error', str(exc))