"""Behavior tests for the screenshot dispatcher and model-safe response formatting."""
import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from observer import Observer
    from observation import Calibration
    from PIL import Image
except ImportError:
    Observer = None


@unittest.skipUnless(Observer, 'observer dependencies unavailable in this environment')
class ObserverTests(unittest.TestCase):
    def test_latest_frame_is_a_single_slot_not_a_backlog(self):
        class FakeOCR:
            def recognize(self, image):
                return []
        counter = [0]
        def fake_capture(rect):
            counter[0] += 1
            return Image.new('RGB', (800, 450), (counter[0] % 255, 42, 75))
        with tempfile.TemporaryDirectory() as folder:
            observer = Observer(1, {'left':0,'top':0,'width':800,'height':450}, Calibration(),
                                Path(folder), .3, .6, ocr_factory=FakeOCR, capture=fake_capture)
            observer.start()
            time.sleep(.75)
            observer.stop()
            observer.thread.join(2)
            serial, image = observer.latest()
            self.assertGreaterEqual(serial, 2)
            self.assertEqual(image.size, (800, 450))
            self.assertIsNone(observer.latest(serial)[1])
            self.assertLessEqual(observer.events.qsize(), 4)

    def test_stop_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            observer = Observer(4, {'left':0,'top':0,'width':100,'height':100}, Calibration(), Path(folder))
            observer.stop()
            observer.stop()
            self.assertTrue(observer.stop_event.is_set())


try:
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QMessageBox
    from desktop_ui import CoachWindow, summarize_result
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication, 'PySide6 UI tests run on CI where Qt wheels are installed')
class DesktopUITests(unittest.TestCase):
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
            self.window.end_game()
        self.window.close()

    def test_initial_layout_has_preview_chat_and_lifecycle(self):
        self.assertIsNotNone(self.window.preview)
        self.assertIsNotNone(self.window.chat)
        self.assertFalse(self.window.end_btn.isEnabled())
        self.assertTrue(self.window.start_btn.isEnabled())
        self.assertFalse(self.window.settings.isVisible())

    def test_session_reset_and_end_save_local_only(self):
        self.window.rect = {'left': 0, 'top': 0, 'width': 800, 'height': 450}
        with patch.object(self.window, 'start_observer'):
            self.window.start_game()
        self.assertEqual(self.window.session.phase, 'active')
        self.assertFalse(self.window.start_btn.isEnabled())
        self.assertTrue(self.window.end_btn.isEnabled())
        self.window.end_game()
        self.assertEqual(self.window.session.phase, 'ended')
        summaries = list(Path(self.folder.name).glob('game_*.json'))
        self.assertEqual(len(summaries), 1)
        self.assertNotIn('api_key', summaries[0].read_text())

    def test_question_answer_and_followup_are_separate(self):
        self.window.rect = {'left': 0, 'top': 0, 'width': 800, 'height': 450}
        with patch.object(self.window, 'start_observer'):
            self.window.start_game()
        self.window.session.pending = 'health'
        self.window.show_question('health', '血量是多少？')
        self.assertFalse(self.window.chat_input.isReadOnly())
        self.window.question_input.setText('26')
        self.window.reply_question()
        self.assertEqual(self.window.session.current('health'), '26')
        self.assertEqual(self.window.session.pending, '')

    def test_no_cloud_call_without_explicit_image_authorization(self):
        self.window.rect = {'left': 0, 'top': 0, 'width': 800, 'height': 450}
        with patch.object(self.window, 'start_observer'):
            self.window.start_game()
        self.window.key.setText('secret')
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            with patch('desktop_ui.analyze') as call:
                self.window.vision_once()
        call.assert_not_called()
        self.assertEqual(self.window.session.counts['model'], 0)

    def test_late_results_cannot_modify_a_new_session(self):
        self.window.rect = {'left':0,'top':0,'width':800,'height':450}
        with patch.object(self.window, 'start_observer'):
            self.window.start_game()
        old = (self.window.run_id, self.window.model_epoch)
        self.window.end_game()
        with patch.object(self.window, 'start_observer'):
            self.window.start_game()
        self.window.model_results.put((*old, 'model', ('text','常规建议',{'action':'旧局建议'})))
        self.window.drain()
        self.assertEqual(self.window.session.last_decision, '')

    def test_untrusted_text_rendered_without_html_interpretation(self):
        self.window.append_message('assistant','<script>bad</script>')
        self.assertIn('<script>bad</script>', self.window.chat.history[-1][1])


class PresentationFormattingTests(unittest.TestCase):
    def test_incomplete_model_data_never_claims_facts(self):
        if QApplication is None:
            self.skipTest('Qt unavailable')
        self.assertEqual(summarize_result({}), '模型没有返回可解析的 JSON 建议。')
        self.assertIn('建议：升本', summarize_result({'action':'升本'}))
        self.assertNotIn('依据：', summarize_result({'action':'升本'}))

if __name__ == '__main__':
    unittest.main()