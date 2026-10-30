"""Regression coverage for local recognition failures and usable AI fallbacks."""
import io
import json
import os
import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image
from local_ocr import OCRLine
from observation import Calibration, ROI
from observer import Observer
from session import GameSession
from providers import request


class ObserverRecoveryTests(unittest.TestCase):
    @staticmethod
    def sample(_):
        return Image.new('RGB', (400, 200), (245, 245, 245))

    def test_ocr_initializer_failure_keeps_screen_preview_alive(self):
        def broken_ocr():
            raise RuntimeError('OCR model initialization failed')
        with tempfile.TemporaryDirectory() as folder:
            watcher = Observer(1, {'left':0,'top':0,'width':400,'height':200},
                               Calibration(), Path(folder), .3, .6,
                               ocr_factory=broken_ocr, capture=self.sample)
            watcher.start()
            time.sleep(.7)
            watcher.stop()
            watcher.thread.join(3)
            serial, frame = watcher.latest()
            self.assertGreaterEqual(serial, 2)
            self.assertEqual(frame.size, (400, 200))
            kinds = [event[0] for event in list(watcher.events.queue)]
            self.assertIn('ocr_error', kinds)

    def test_calibrated_number_can_be_read_without_a_field_label(self):
        class FakeOCR:
            def recognize(self, image):
                if image.size == (160, 80):
                    return [OCRLine('26', .98, ((0,0),(20,0),(20,20),(0,20)))]
                return []
        with tempfile.TemporaryDirectory() as folder:
            watcher = Observer(2, {'left':0,'top':0,'width':400,'height':200},
                               Calibration({'health': ROI(.1, .1, .2, .2)}),
                               Path(folder), .3, .6, ocr_factory=FakeOCR,
                               capture=self.sample)
            watcher.start()
            time.sleep(.36)
            watcher.stop()
            watcher.thread.join(3)
            result = [data for kind,data in list(watcher.events.queue) if kind=='ocr']
            self.assertTrue(result)
            lines, scoped, icons = result[0]
            session = GameSession()
            session.start()
            session.observe(lines, scoped=scoped)
            self.assertEqual(session.current('health'), '26')

    def test_unlabeled_screen_number_without_roi_is_not_a_health_fact(self):
        game = GameSession()
        game.start()
        game.observe([OCRLine('26', .99)])
        self.assertIsNone(game.current('health'))

    def test_ambiguous_numbers_within_roi_are_rejected(self):
        game = GameSession()
        game.start()
        lines = [OCRLine('26', .95), OCRLine('28', .95)]
        game.observe(lines, scoped={'health':lines, 'energy':[], 'round':[], 'weapon':[]})
        self.assertIsNone(game.current('health'))


class ProviderErrorTests(unittest.TestCase):
    def test_http_error_exposes_message_but_redacts_secret(self):
        body = json.dumps({'error': {'message':'invalid model or token SECRET'}}).encode()
        err = HTTPError('https://example.invalid', 400, 'bad request', {}, io.BytesIO(body))
        with patch('urllib.request.urlopen', side_effect=err):
            with self.assertRaises(RuntimeError) as cm:
                request('https://example.invalid', {'messages': []}, 'SECRET')
        self.assertIn('400', str(cm.exception))
        self.assertIn('invalid model', str(cm.exception))
        self.assertNotIn('SECRET', str(cm.exception))


os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from desktop_ui import CoachWindow
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, 'PySide6 not installed')
class DesktopRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.window = CoachWindow(session_dir=self.folder.name)
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        if self.window.session.phase == 'active':
            self.window.session.end()
        self.window.observer = None
        self.window.close()

    def test_manual_advice_visible_and_works_with_empty_ocr(self):
        self.assertIsNotNone(self.window.advise_btn)
        self.window.session.start()
        self.window.rect = {'left':0,'top':0,'width':400,'height':200}
        with patch.object(self.window, 'launch_model', return_value=True) as called:
            self.window.advise_once()
        called.assert_called_once_with('text')

    def test_explicitly_enabled_auto_ai_does_not_stall_on_empty_ocr(self):
        self.window.auto_text.blockSignals(True)
        self.window.auto_text.setChecked(True)
        self.window.auto_text.blockSignals(False)
        self.window.cloud_text_allowed = True
        self.window.session.start()
        self.window.session.counts['ocr'] = 1
        with patch.object(self.window, 'launch_model', return_value=True) as called:
            self.window.maybe_model()
            self.window.maybe_model()
        called.assert_called_once_with('text')

    def test_visible_ocr_failure_explains_missing_model_result(self):
        self.window.session.start()
        class BrokenObserver:
            run_id = self.window.run_id
            events = queue.Queue()
            def latest(self, seen):
                return seen, None
        broken = BrokenObserver()
        broken.events.put(('ocr_error', 'RuntimeError: broken OCR'))
        self.window.observer = broken
        with patch.object(self.window, 'maybe_model'):
            self.window.drain()
        self.assertIn('OCR', self.window.status.text())
        self.assertTrue(any('broken OCR' in msg for _,msg in self.window.chat.history))
        self.window.observer = None


if __name__ == '__main__':
    unittest.main()
