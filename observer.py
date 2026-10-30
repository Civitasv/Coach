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
from dataclasses import replace

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
        self.ocr_failures = 0

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
        """Capture must survive unavailable or failed local OCR.

        Initialization/downloads can be slow; a failed OCR call must not blank
        the preview or make the UI silently stop receiving frames.
        """
        try:
            matcher = IconMatcher.from_directory(self.templates_dir)
            ocr = None
            retry_at = 0.0
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
                    try:
                        if ocr is None and started >= retry_at:
                            self._event('ocr_status', 'Initializing local OCR...')
                            ocr = self.ocr_factory()
                            self.ocr_failures = 0
                        if ocr is not None:
                            lines = ocr.recognize(image)
                            scoped = scoped_lines(lines, self.calibration, *image.size) if self.calibration.regions else None
                            if scoped is not None:
                                # Small HUD numerals can vanish when full-screen images
                                # are resized for OCR. Re-read only calibrated tiny ROIs.
                                for name in ('health', 'energy', 'round', 'weapon'):
                                    roi = self.calibration.regions.get(name)
                                    if roi is None:
                                        continue
                                    box = roi.pixels(*image.size)
                                    crop = image.crop(box)
                                    if crop.width < 20 or crop.height < 12:
                                        continue
                                    scale = 2 if crop.height < 120 else 1
                                    if scale > 1:
                                        crop = crop.resize((crop.width*scale, crop.height*scale))
                                    small_lines = ocr.recognize(crop)
                                    adjusted = []
                                    for line in small_lines:
                                        box_points = tuple((round(x/scale)+box[0], round(y/scale)+box[1])
                                                           for x,y in line.box) if line.box else ()
                                        adjusted.append(replace(line, box=box_points))
                                    scoped[name] = adjusted
                                    lines.extend(adjusted)
                            icons = {}
                            for name, roi in self.calibration.regions.items():
                                if name.startswith('shop_slot_') or name == 'enemy_icon':
                                    try:
                                        icons[name] = matcher.classify(image.crop(roi.pixels(*image.size)))
                                    except ValueError:
                                        pass
                            self._event('ocr', (lines, scoped, icons))
                            self.ocr_failures = 0
                    except Exception as exc:
                        self.ocr_failures += 1
                        self._event('ocr_error', f'{type(exc).__name__}: {str(exc)[:180]}')
                        # Recreate OCR after a failed invocation, throttled to avoid
                        # an expensive tight loop or repeated model downloads.
                        ocr = None
                        retry_at = time.monotonic() + 20.
                    next_ocr = time.monotonic() + self.ocr_interval
                    refresh_at = time.monotonic() + 8.
                self.stop_event.wait(max(0., self.sample_interval - (time.monotonic() - started)))
        except Exception as exc:
            self._event('error', f'{type(exc).__name__}: {exc}')
