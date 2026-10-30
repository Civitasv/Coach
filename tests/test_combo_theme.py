"""Regression: combo labels and popup options stay legible on Windows dark themes."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QStyleFactory
    from desktop_ui import CoachWindow
except ImportError:
    QApplication = None


def luminance(color):
    channels = [color.redF(), color.greenF(), color.blueF()]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
              for c in channels]
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]


def contrast(first, second):
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + .05) / (b + .05)


@unittest.skipUnless(QApplication, 'Qt is unavailable')
class ComboBoxThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        self.original_palette = self.app.palette()
        dark = QPalette(self.original_palette)
        dark.setColor(QPalette.ColorRole.Window, QColor('#181B24'))
        dark.setColor(QPalette.ColorRole.Base, QColor('#161921'))
        dark.setColor(QPalette.ColorRole.Text, QColor('#FFFFFF'))
        dark.setColor(QPalette.ColorRole.Button, QColor('#FDFDFD'))
        dark.setColor(QPalette.ColorRole.ButtonText, QColor('#FFFFFF'))
        dark.setColor(QPalette.ColorRole.Highlight, QColor('#142030'))
        dark.setColor(QPalette.ColorRole.HighlightedText, QColor('#FFFFFF'))
        self.app.setPalette(dark)
        self.window = CoachWindow()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.setPalette(self.original_palette)

    def test_all_dropdowns_have_contrasting_current_text_and_list_items(self):
        for combo in (self.window.provider, self.window.mode, self.window.roi_combo, self.window.monitor_combo):
            with self.subTest(combo=combo.objectName() or combo.currentText()):
                combo.ensurePolished()
                combo.view().ensurePolished()
                combo_palette = combo.palette()
                popup_palette = combo.view().palette()
                self.assertGreaterEqual(
                    contrast(combo_palette.color(QPalette.ColorRole.Text),
                             combo_palette.color(QPalette.ColorRole.Base)),
                    4.5, 'Collapsed combo foreground and background must contrast')
                self.assertGreaterEqual(
                    contrast(popup_palette.color(QPalette.ColorRole.Text),
                             popup_palette.color(QPalette.ColorRole.Base)),
                    4.5, 'Popup option labels must remain readable in dark OS mode')
                self.assertGreaterEqual(
                    contrast(popup_palette.color(QPalette.ColorRole.HighlightedText),
                             popup_palette.color(QPalette.ColorRole.Highlight)),
                    4.5, 'Selected option label must contrast with its highlight')

    def test_popup_remains_readable_after_changing_selection(self):
        combo = self.window.provider
        combo.setCurrentIndex(1)
        self.assertEqual(combo.currentText(), 'Ollama 本地')
        combo.showPopup()
        self.app.processEvents()
        popup = combo.view().palette()
        self.assertGreaterEqual(
            contrast(popup.color(QPalette.ColorRole.Text),
                     popup.color(QPalette.ColorRole.Base)), 4.5)
        combo.hidePopup()


if __name__ == '__main__':
    unittest.main()
