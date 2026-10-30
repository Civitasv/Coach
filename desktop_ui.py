"""PySide6 desktop shell. All game state changes happen on the Qt UI thread."""
import json
import os
import queue
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import mss
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QDoubleSpinBox, QSplitter,
    QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from advice import offline_hint, text_prompt
from engine import parse, prompt, short
from observation import Calibration, ROI, ROI_NAMES
from observer import Observer, grab, jpeg
from providers import analyze, analyze_text
from qt_widgets import ChatFeed, GamePreview, RegionPicker
from session import GameSession, LABELS

PROVIDERS = {'DeepSeek 云端': ('deepseek-flash', 'DEEPSEEK_API_KEY'),
             'Ollama 本地': ('gemma3:4b', ''),
             'OpenAI 云端': ('gpt-4.1-mini', 'OPENAI_API_KEY')}
MODES = ('常规建议', '牌库扫描', '对手侦察')
APP_CSS = """
QMainWindow, QWidget#AppSurface { background: #F5F6F8; color: #222B3B; }
QFrame#Panel, QFrame#Toolbar, QFrame#StatCard, QFrame#QuestionCard, QFrame#Settings {
 background: #FFFFFF; border: 1px solid #E7EAF0; border-radius: 14px;
}
QFrame#AssistantBubble { background: #FFFFFF; border: 1px solid #E6EAF0; border-radius: 15px; }
QFrame#UserBubble { background: #EAF2FF; border: 1px solid #DFEAFC; border-radius: 15px; }
QFrame#SystemBubble { background: #F2F4F7; border: 1px solid #E9EDF2; border-radius: 13px; }
QWidget#ChatSurface, QScrollArea#ChatFeed { background: #F8F9FB; border: none; }
QLabel#Brand { font-size: 22px; font-weight: 700; color: #202B3B; }
QLabel#Heading { font-size: 14px; font-weight: 650; color: #263244; }
QLabel#Muted, QLabel#StatName, QLabel#ChatNote { color: #768397; font-size: 11px; }
QLabel#StatValue { font-size: 20px; font-weight: 700; color: #263244; }
QLabel#ChatSpeaker { color: #566E90; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLabel#ChatBody { color: #293446; font-size: 13px; line-height: 1.5; }
QLabel#Status { color: #66768B; font-size: 11px; }
QPushButton { background: #FFFFFF; color: #40506B; border: 1px solid #DEE4EC;
 border-radius: 9px; padding: 8px 13px; font-size: 12px; }
QPushButton:hover { background: #F1F5FA; border-color: #CCD8E8; }
QPushButton:disabled { color: #AEB8C5; background: #F8F9FB; }
QPushButton#PrimaryButton { background: #2B6EDE; color: white; font-weight: 650; border: 1px solid #2B6EDE; }
QPushButton#PrimaryButton:hover { background: #1C5FCE; }
QPushButton#DangerButton { border: 1px solid #F0CDCF; color: #B5474A; background: #FFF8F8; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QTextEdit {
 background: #FFFFFF; color: #243044; border: 1px solid #DFE5EE;
 border-radius: 9px; padding: 7px; selection-background-color: #DBE9FF;
}
QLineEdit:focus, QTextEdit:focus { border: 1px solid #71A6F1; }
QTextEdit#Composer { border-radius: 12px; }
QTextEdit#OCRText { background: #FAFBFD; border: none; color: #647187; font-family: Consolas; }
QScrollBar:vertical { background: #F8F9FB; width: 7px; margin: 0; }
QScrollBar::handle:vertical { background: #D7DDE6; min-height: 40px; border-radius: 3px; }
QSplitter::handle { background: #F5F6F8; width: 12px; }
QCheckBox { color: #586A80; }
"""


def title(text, name='Heading'):
    label = QLabel(text)
    label.setObjectName(name)
    return label


def button(text, callback, kind=None):
    control = QPushButton(text)
    if kind:
        control.setObjectName(kind)
    control.clicked.connect(callback)
    return control


def frame_panel(layout=None, name='Panel'):
    panel = QFrame()
    panel.setObjectName(name)
    if layout is not None:
        panel.setLayout(layout)
    return panel


def vertical(parent=None, margins=(14, 14, 14, 14), spacing=10):
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def horizontal(parent=None, margins=(0, 0, 0, 0), spacing=8):
    layout = QHBoxLayout(parent)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def summarize_result(result):
    """The model response is external data; never promote unverified claims to facts."""
    if not isinstance(result, dict) or not result:
        return '模型没有返回可解析的 JSON 建议。'
    fields = [('建议', 'action'), ('依据', 'observed'), ('备选', 'alternative'),
              ('风险', 'risk'), ('置信度', 'confidence')]
    parts = []
    for label, key in fields:
        value = short(result.get(key), 350)
        if value:
            parts.append(f'{label}：{value}')
    return '\n\n'.join(parts) if parts else '模型没有给出可展示的建议。'


class CoachWindow(QMainWindow):
    def __init__(self, parent=None, session_dir=None):
        super().__init__(parent)
        self.setWindowTitle('Coach  ·  AI 对局教练')
        self.resize(1420, 890)
        self.setMinimumSize(1050, 710)
        self.session = GameSession()
        self.session_dir = Path(session_dir) if session_dir else Path(__file__).resolve().parent / 'sessions'
        self.config_dir = Path(__file__).resolve().parent / 'config'
        self.calibration_file = self.config_dir / 'calibration.json'
        try:
            self.calibration = Calibration.load(self.calibration_file) if self.calibration_file.exists() else Calibration()
        except (OSError, ValueError, KeyError, TypeError):
            self.calibration = Calibration()
        self.rect = None
        self.monitors = []
        self.observer = None
        self.last_frame_seq = 0
        self.capture_count_seen = 0
        self.run_id = 0
        self.model_epoch = 0
        self.model_results = queue.Queue()
        self.model_busy = False
        self.cloud_text_allowed = False
        self.last_fingerprint = ''
        self.last_text_at = 0
        self.shown_question = ''
        self.latest_frame = None
        self.ocr_empty_notice = False
        self.ocr_error_notice = ''
        self.messages = []
        self.build_ui()
        self.refresh_monitors()
        self.append_message('assistant',
            '先框选游戏区域并开始本局。配置 API Key 不会自动调用模型；'
            '点击顶部「立即获取建议」，或展开设置并启用「自动建议」才能发起调用。'
            'OCR 看不到关键数据时，我会明确问你。')
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.drain)
        self.timer.start(130)

    def build_ui(self):
        self.setStyleSheet(APP_CSS)
        shell = QWidget()
        shell.setObjectName('AppSurface')
        self.setCentralWidget(shell)
        outer = vertical(shell, (22, 16, 22, 18), 12)

        head = horizontal(spacing=12)
        head.addWidget(title('Coach', 'Brand'))
        head.addWidget(title('LOCAL FIRST · 只读辅助', 'Muted'))
        head.addStretch()
        self.phase = title('未开始', 'Muted')
        head.addWidget(self.phase)
        self.settings_btn = button('设置与校准', self.toggle_settings)
        head.addWidget(self.settings_btn)
        self.pick_btn = button('框选游戏区域', self.pick)
        head.addWidget(self.pick_btn)
        self.advise_btn = button('立即获取建议', self.advise_once)
        head.addWidget(self.advise_btn)
        self.start_btn = button('开始本局', self.start_game, 'PrimaryButton')
        head.addWidget(self.start_btn)
        self.pause_btn = button('暂停', self.toggle_pause)
        self.pause_btn.setEnabled(False)
        head.addWidget(self.pause_btn)
        self.end_btn = button('结束本局', self.end_game, 'DangerButton')
        self.end_btn.setEnabled(False)
        head.addWidget(self.end_btn)
        outer.addLayout(head)

        self.settings = frame_panel(name='Settings')
        settings = vertical(self.settings, (16, 12, 16, 12), 9)
        line1 = horizontal(spacing=9)
        self.monitor_combo = QComboBox()
        self.monitor_combo.setMinimumWidth(210)
        line1.addWidget(title('显示器', 'Muted'))
        line1.addWidget(self.monitor_combo)
        line1.addWidget(button('刷新', self.refresh_monitors))
        line1.addSpacing(12)
        line1.addWidget(title('模型', 'Muted'))
        self.provider = QComboBox()
        self.provider.addItems(PROVIDERS)
        self.provider.currentTextChanged.connect(self.provider_changed)
        line1.addWidget(self.provider)
        self.model = QLineEdit('deepseek-flash')
        self.model.setMaximumWidth(175)
        line1.addWidget(self.model)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText('API Key（只保存在内存）')
        line1.addWidget(self.key, 1)
        settings.addLayout(line1)
        line2 = horizontal(spacing=10)
        self.auto_text = QCheckBox('局面变化时自动请求 AI 文字建议')
        self.auto_text.toggled.connect(self.on_auto_text)
        line2.addWidget(self.auto_text)
        line2.addWidget(title('模型间隔', 'Muted'))
        self.model_delay = QDoubleSpinBox()
        self.model_delay.setRange(10, 180)
        self.model_delay.setSuffix(' s')
        self.model_delay.setValue(12.)
        line2.addWidget(self.model_delay)
        line2.addWidget(title('采样', 'Muted'))
        self.sample_delay = QDoubleSpinBox()
        self.sample_delay.setRange(.3, 5.)
        self.sample_delay.setSingleStep(.1)
        self.sample_delay.setValue(.5)
        line2.addWidget(self.sample_delay)
        line2.addWidget(title('OCR', 'Muted'))
        self.ocr_delay = QDoubleSpinBox()
        self.ocr_delay.setRange(.6, 30.)
        self.ocr_delay.setValue(1.5)
        line2.addWidget(self.ocr_delay)
        line2.addWidget(title('调用上限', 'Muted'))
        self.call_limit = QSpinBox()
        self.call_limit.setRange(1, 2000)
        self.call_limit.setValue(100)
        line2.addWidget(self.call_limit)
        settings.addLayout(line2)
        line3 = horizontal(spacing=9)
        line3.addWidget(title('扫描类型', 'Muted'))
        self.mode = QComboBox()
        self.mode.addItems(MODES)
        line3.addWidget(self.mode)
        self.vision_btn = button('深度看图一次（单独授权）', self.vision_once)
        line3.addWidget(self.vision_btn)
        line3.addSpacing(12)
        line3.addWidget(title('校准', 'Muted'))
        self.roi_combo = QComboBox()
        self.roi_combo.addItems(sorted(ROI_NAMES))
        line3.addWidget(self.roi_combo)
        line3.addWidget(button('框选 ROI', self.pick_roi))
        line3.addWidget(button('清除 ROI', self.remove_roi))
        line3.addWidget(button('保存英雄模板', self.save_icon_template))
        line3.addStretch()
        settings.addLayout(line3)
        self.settings.hide()
        outer.addWidget(self.settings)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)
        self.build_left(splitter)
        self.build_right(splitter)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([840, 560])
        self.status = title('本地 OCR 待命 · 截图与 Key 不会自动上传', 'Status')
        outer.addWidget(self.status)

    def build_left(self, splitter):
        panel = frame_panel(name='Panel')
        splitter.addWidget(panel)
        col = vertical(panel, (18, 17, 18, 16), 13)
        row = horizontal(spacing=8)
        row.addWidget(title('实时画面'))
        row.addStretch()
        self.capture_status = title('未连接', 'Muted')
        row.addWidget(self.capture_status)
        col.addLayout(row)
        self.preview = GamePreview()
        col.addWidget(self.preview, 5)
        head = horizontal(spacing=8)
        head.addWidget(title('当前局面'))
        head.addStretch()
        self.counters = title('截图 0 · OCR 0 · AI 0', 'Muted')
        head.addWidget(self.counters)
        col.addLayout(head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.facts = {}
        for index, (key, label) in enumerate([('health','血量'),('energy','能量'),('round','回合'),('weapon','武器')]):
            card = frame_panel(name='StatCard')
            box = vertical(card, (12, 10, 12, 10), 5)
            box.addWidget(title(label, 'StatName'))
            value = title('未知', 'StatValue')
            box.addWidget(value)
            grid.addWidget(card, index // 4, index % 4)
            self.facts[key] = value
        col.addLayout(grid)
        self.shop_label = title('商店  ·  未校准 / 未识别', 'Muted')
        self.shop_label.setWordWrap(True)
        col.addWidget(self.shop_label)
        self.enemy_label = title('对手  ·  暂无可靠信息', 'Muted')
        self.enemy_label.setWordWrap(True)
        col.addWidget(self.enemy_label)
        self.ocr_toggle = QToolButton()
        self.ocr_toggle.setText('查看 OCR 原始文字  ▾')
        self.ocr_toggle.setCheckable(True)
        self.ocr_toggle.toggled.connect(self.toggle_ocr)
        col.addWidget(self.ocr_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self.ocr_view = QTextEdit()
        self.ocr_view.setReadOnly(True)
        self.ocr_view.setObjectName('OCRText')
        self.ocr_view.setMaximumHeight(128)
        self.ocr_view.hide()
        col.addWidget(self.ocr_view)

    def build_right(self, splitter):
        panel = frame_panel(name='Panel')
        splitter.addWidget(panel)
        col = vertical(panel, (0, 0, 0, 0), 0)
        head = QWidget()
        h = horizontal(head, (18, 14, 18, 12), 8)
        h.addWidget(title('教练对话'))
        h.addStretch()
        h.addWidget(title('可追问 · 可直接补充信息', 'Muted'))
        col.addWidget(head)
        self.chat = ChatFeed()
        col.addWidget(self.chat, 1)
        self.question_card = frame_panel(name='QuestionCard')
        q = vertical(self.question_card, (14, 12, 14, 12), 7)
        q.addWidget(title('需要你补充', 'Heading'))
        self.question_label = QLabel()
        self.question_label.setWordWrap(True)
        q.addWidget(self.question_label)
        ans = horizontal(spacing=7)
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText('输入准确数值或文字')
        self.question_input.returnPressed.connect(self.reply_question)
        ans.addWidget(self.question_input, 1)
        ans.addWidget(button('回答', self.reply_question, 'PrimaryButton'))
        ans.addWidget(button('跳过', self.skip_question))
        q.addLayout(ans)
        self.question_card.hide()
        col.addWidget(self.question_card)
        composer = QWidget()
        c = vertical(composer, (16, 12, 16, 16), 8)
        self.chat_input = QTextEdit()
        self.chat_input.setObjectName('Composer')
        self.chat_input.setPlaceholderText('继续追问香香的运营、武器选择、变阵时机…')
        self.chat_input.setMaximumHeight(90)
        c.addWidget(self.chat_input)
        row = horizontal(spacing=8)
        row.addWidget(title('Ctrl + Enter 发送 · 本地 OCR 免费', 'Muted'))
        row.addStretch()
        self.send_btn = button('发送消息', self.send_chat, 'PrimaryButton')
        row.addWidget(self.send_btn)
        c.addLayout(row)
        col.addWidget(composer)
        self.chat_input.installEventFilter(self)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent
        if (watched is self.chat_input and event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.send_chat()
            return True
        return super().eventFilter(watched, event)

    def toggle_settings(self):
        self.settings.setVisible(not self.settings.isVisible())

    def toggle_ocr(self, checked):
        self.ocr_view.setVisible(checked)
        self.ocr_toggle.setText('收起 OCR 原始文字  ▴' if checked else '查看 OCR 原始文字  ▾')

    def append_message(self, role, message, note=''):
        self.chat.append(role, message, note)
        if role != 'system':
            self.messages.append((role, short(message, 600)))
            self.messages = self.messages[-18:]

    def refresh_monitors(self):
        try:
            with mss.mss() as screen:
                self.monitors = [dict(m) for m in screen.monitors[1:]]
            self.monitor_combo.clear()
            self.monitor_combo.addItems([f'显示器 {i+1} · {m["width"]}×{m["height"]}'
                                         for i,m in enumerate(self.monitors)])
        except Exception as exc:
            self.status.setText('无法获取显示器：' + str(exc)[:130])

    def pick_area(self, source, minimum=100):
        try:
            dialog = RegionPicker(self, source, grab)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selection:
                if dialog.selection['width'] >= minimum and dialog.selection['height'] >= (70 if minimum > 12 else 12):
                    return dialog.selection
                QMessageBox.warning(self, '区域过小', '请框选更大的区域。')
        except Exception as exc:
            QMessageBox.warning(self, '选区失败', str(exc)[:250])
        return None

    def pick(self):
        if self.observer:
            self.pause_observer()
        if not self.monitors:
            return
        selected = self.pick_area(self.monitors[max(0, self.monitor_combo.currentIndex())])
        if selected:
            self.rect = selected
            self.status.setText(f'监看区域：{selected["width"]}×{selected["height"]} · 已就绪')

    def pick_roi(self):
        if not self.rect:
            QMessageBox.information(self, '先选择游戏区域', '请先选择整个游戏画面，再框选具体的识别区域。')
            return
        if self.observer:
            self.pause_observer()
        selected = self.pick_area(self.rect, minimum=12)
        if not selected:
            return
        game = self.rect
        try:
            roi = ROI((selected['left']-game['left'])/game['width'],
                      (selected['top']-game['top'])/game['height'],
                      selected['width']/game['width'], selected['height']/game['height'])
            self.calibration.regions[self.roi_combo.currentText()] = roi
            self.calibration.save(self.calibration_file)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, '保存失败', str(exc))
            return
        self.status.setText('ROI 已本地保存 · 恢复监看后生效')

    def remove_roi(self):
        if self.observer:
            self.pause_observer()
        self.calibration.regions.pop(self.roi_combo.currentText(), None)
        try:
            self.calibration.save(self.calibration_file)
            self.status.setText('已删除该 ROI')
        except OSError as exc:
            self.status.setText('ROI 保存失败：' + str(exc))

    def save_icon_template(self):
        name = self.roi_combo.currentText()
        if not self.rect or (not name.startswith('shop_slot_') and name != 'enemy_icon'):
            QMessageBox.warning(self, '需要图标区域', '请先校准 shop_slot_1…5 或 enemy_icon。')
            return
        roi = self.calibration.regions.get(name)
        if roi is None:
            QMessageBox.warning(self, '尚未校准', '请先框选对应图标区域。')
            return
        hero, ok = QInputDialog.getText(self, '保存图标样本', '英雄名称（必须人工确认）：')
        if not ok or not hero:
            return
        if not re.fullmatch(r'[\w\u4e00-\u9fff-]{1,30}', hero):
            QMessageBox.warning(self, '名称无效', '请使用中文、字母、数字、下划线或短横线。')
            return
        path = self.config_dir / 'icon_templates' / f'{hero}.png'
        if path.exists() and QMessageBox.question(self, '覆盖模板', f'覆盖 {hero} 的既有模板？') != QMessageBox.StandardButton.Yes:
            return
        if self.observer:
            self.pause_observer()
        try:
            img = grab(self.rect)
            path.parent.mkdir(parents=True, exist_ok=True)
            img.crop(roi.pixels(*img.size)).save(path)
            self.status.setText('本地图标样本已保存 · 恢复观察后生效')
        except (ValueError, OSError) as exc:
            self.status.setText('图标保存失败：' + str(exc)[:140])

    def provider_changed(self, provider):
        self.model.setText(PROVIDERS[provider][0])
        self.key.clear()
        self.cloud_text_allowed = False
        self.auto_text.blockSignals(True)
        self.auto_text.setChecked(False)
        self.auto_text.blockSignals(False)
        self.model_epoch += 1
        self.model_busy = False
        self.status.setText('模型已切换。云端文字和截图授权均须重新确认。')

    def provider_key(self):
        name = PROVIDERS[self.provider.currentText()][1]
        return self.key.text().strip() or os.environ.get(name, '').strip()

    def authorize_text(self):
        if self.provider.currentText() != 'Ollama 本地':
            if not self.provider_key():
                QMessageBox.warning(self, '未配置 API Key', '请填写 API Key。无需 API Key 也能本地 OCR。')
                return False
            answer = QMessageBox.question(self, '授权发送文字',
                '将向云端发送本局 OCR 文字和已确认的状态，不发送截图。允许本局持续请求吗？')
            if answer != QMessageBox.StandardButton.Yes:
                return False
        self.cloud_text_allowed = True
        return True

    def on_auto_text(self, checked):
        if not checked:
            self.cloud_text_allowed = False
        elif self.session.phase == 'active' and not self.authorize_text():
            self.auto_text.blockSignals(True)
            self.auto_text.setChecked(False)
            self.auto_text.blockSignals(False)

    def start_game(self):
        if not self.rect:
            QMessageBox.warning(self, '未选择画面', '请先点击「框选游戏区域」。')
            return
        if self.session.phase == 'active':
            return
        self.stop_observer()
        self.session.start()
        self.model_epoch += 1
        self.model_busy = False
        self.last_fingerprint = ''
        self.last_text_at = 0
        self.shown_question = ''
        self.ocr_empty_notice = False
        self.ocr_error_notice = ''
        self.messages = []
        self.chat.clear_messages()
        self.preview.set_image(None)
        self.reset_question()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.end_btn.setEnabled(True)
        self.phase.setText('对局中 · 本地识别')
        if self.auto_text.isChecked() and not self.authorize_text():
            self.auto_text.blockSignals(True)
            self.auto_text.setChecked(False)
            self.auto_text.blockSignals(False)
        self.append_message('system','本局开始 · 已清空上局状态和模型调用计数')
        self.append_message('assistant','开始监看。如果缺少血量、武器或对手信息，我会在这里主动问你。')
        self.refresh_state()
        self.start_observer()

    def stop_observer(self):
        self.run_id += 1
        self.model_epoch += 1
        self.model_busy = False
        if self.observer:
            self.observer.stop()
            self.observer = None

    def start_observer(self):
        if self.observer or self.session.phase != 'active' or not self.rect:
            return
        self.run_id += 1
        self.capture_count_seen = 0
        self.last_frame_seq = 0
        self.observer = Observer(self.run_id, self.rect,
            Calibration(dict(self.calibration.regions)), self.config_dir / 'icon_templates',
            self.sample_delay.value(), self.ocr_delay.value())
        self.observer.start()
        self.pause_btn.setText('暂停')
        self.capture_status.setText('● 观察中')
        self.status.setText('本地高频看屏 · OCR 在本机执行')

    def pause_observer(self):
        if not self.observer:
            return
        self.stop_observer()
        self.pause_btn.setText('继续')
        self.capture_status.setText('已暂停')
        self.status.setText('观察已暂停。识别状态保留，但时间过期的数据将显示未知。')

    def toggle_pause(self):
        if self.session.phase != 'active':
            return
        if self.observer:
            self.pause_observer()
        else:
            self.start_observer()

    def end_game(self):
        if not self.session.end():
            return
        self.stop_observer()
        self.auto_text.blockSignals(True)
        self.auto_text.setChecked(False)
        self.auto_text.blockSignals(False)
        self.cloud_text_allowed = False
        self.reset_question()
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText('暂停')
        self.end_btn.setEnabled(False)
        self.phase.setText('本局已结束')
        self.capture_status.setText('已停止')
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            dest = self.session_dir / f'game_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.json'
            dest.write_text(json.dumps(self.session.summary(), ensure_ascii=False, indent=2), encoding='utf-8')
            self.status.setText(f'本局摘要已保存到 {dest.name} · 不包含截图或 API Key')
        except OSError as exc:
            self.status.setText('本局已结束，但保存摘要失败：' + str(exc)[:130])
        self.append_message('system', '本局结束 · 截图和模型请求已停止。下局点击「开始本局」。')

    def show_question(self, field, question):
        if question == self.shown_question:
            return
        self.shown_question = question
        self.question_label.setText(question)
        self.question_card.show()
        self.append_message('assistant', question, '缺失信息 · 不会擅自猜测')

    def reset_question(self):
        self.question_card.hide()
        self.question_input.clear()
        self.shown_question = ''

    def reply_question(self):
        if self.session.phase != 'active' or not self.session.pending:
            return
        value = self.question_input.text().strip()
        try:
            self.session.reply(self.session.pending, value)
        except ValueError as exc:
            self.status.setText('回答格式不正确：' + str(exc))
            return
        self.append_message('user', value)
        self.append_message('assistant', '收到，这项信息已作为你的确认值写入本局状态。')
        self.reset_question()
        self.last_fingerprint = ''
        self.refresh_state()
        self.maybe_model(force=True)

    def skip_question(self):
        self.session.skip_question()
        self.reset_question()
        self.status.setText('已跳过；后续有必要时会再问。')

    def send_chat(self):
        text = self.chat_input.toPlainText().strip()
        if not text:
            return
        self.chat_input.clear()
        self.append_message('user', text)
        if self.session.phase != 'active':
            self.append_message('assistant', '请先开始一局，才能根据当前识别画面分析。')
            return
        self.launch_model('chat', question=text)

    def advise_once(self):
        """Manually request one text-only decision regardless of OCR availability."""
        if self.session.phase != 'active':
            QMessageBox.information(self, '先开始对局', '请先框选画面并点击「开始本局」。')
            return
        if self.model_busy:
            self.append_message('system', '上一次建议还在生成中。')
            return
        self.launch_model('text')

    def maybe_model(self, force=False):
        if self.session.phase != 'active' or self.model_busy or not self.auto_text.isChecked():
            return
        if not self.cloud_text_allowed or self.session.counts['model'] >= self.call_limit.value():
            return
        # Empty OCR is not a reason to suppress AI forever. The model must
        # explicitly ask for critical missing facts instead of inventing them.
        if self.session.counts['ocr'] < 1 and not force:
            return
        icons = sorted((k,v['name']) for k,v in self.session.fresh_icons().items())
        fingerprint = (self.session.latest_ocr, tuple(icons), tuple((k,self.session.current(k)) for k in LABELS))
        if not force and fingerprint == self.last_fingerprint:
            return
        now = time.monotonic()
        if not force and now - self.last_text_at < self.model_delay.value():
            return
        self.last_fingerprint = fingerprint
        self.last_text_at = now
        self.launch_model('text')

    def vision_once(self):
        if self.session.phase != 'active':
            QMessageBox.information(self, '未开始', '请先开始本局。')
            return
        provider = self.provider.currentText()
        if provider != 'Ollama 本地':
            if not self.provider_key():
                QMessageBox.warning(self, '缺少 API Key', '请先填写 API Key。')
                return
            if QMessageBox.question(self, '确认上传截图',
                    '本次会发送所选游戏区域的真实截图，可能包含昵称等个人信息。确认上传吗？') != QMessageBox.StandardButton.Yes:
                return
        self.launch_model('vision')

    def launch_model(self, kind, question=''):
        if self.session.phase != 'active' or self.model_busy:
            return False
        if self.session.counts['model'] >= self.call_limit.value():
            self.append_message('system', '本局模型调用额度已达上限。')
            return False
        provider = self.provider.currentText()
        if kind != 'vision' and provider != 'Ollama 本地' and not self.cloud_text_allowed:
            if not self.authorize_text():
                return False
        model = self.model.text().strip()
        key = self.provider_key()
        mode = self.mode.currentText()
        if kind == 'vision':
            request_prompt = prompt(mode, self.session.match, self.session.context()[:1500])
        else:
            request_prompt = text_prompt(self.session)
            if kind == 'chat':
                # Keep conversation turns in context without sending screen pixels.
                history = '\n'.join(f'{role}: {content}' for role, content in self.messages[-8:])
                request_prompt += '\n最近对话（不要当作画面事实）：\n' + history[:2200]
                request_prompt += '\n用户本轮问题：' + question[:700]
        self.model_busy = True
        self.session.counts['model'] += 1
        self.refresh_state()
        run, epoch = self.run_id, self.model_epoch
        rect = dict(self.rect)

        def work():
            try:
                if kind == 'vision':
                    result = analyze(provider, jpeg(grab(rect)), request_prompt, model, key)
                else:
                    result = analyze_text(provider, request_prompt, model, key)
                parsed = parse(result)
                if kind != 'vision' and not parsed:
                    if str(result).strip():
                        parsed = {'action': str(result).strip()[:850],
                                  'confidence': 'low',
                                  'risk': '模型输出未遵循约定格式；仅作为未经结构化验证的文字参考。'}
                    else:
                        raise RuntimeError('模型返回空文本。请检查模型名称和 API 配额。')
                self.model_results.put((run, epoch, 'model', (kind, mode, parsed)))
            except Exception as exc:
                self.model_results.put((run, epoch, 'error', str(exc)))
        threading.Thread(target=work, daemon=True, name='CoachLLM').start()
        self.status.setText('教练正在思考…')
        return True

    def refresh_state(self):
        facts = {key: self.session.current(key) or '未知' for key in ('health','energy','round','weapon')}
        for key, label in self.facts.items():
            label.setText(facts[key])
        icons = self.session.fresh_icons()
        shop = [icons.get(f'shop_slot_{i}', {}).get('name', '未知') for i in range(1,6)]
        self.shop_label.setText('商店  ·  ' + '  /  '.join(shop) + '   （本地模板确认；未知不猜）')
        enemy = self.session.current('opponent')
        fragment = icons.get('enemy_icon', {}).get('name')
        self.enemy_label.setText('对手  ·  '+ (enemy or ('图标片段：'+fragment+'（非完整阵容）' if fragment else '暂无可靠信息')))
        self.preview.set_state(facts, shop)
        self.counters.setText(f'截图 {self.session.counts["captures"]} · OCR {self.session.counts["ocr"]} · AI {self.session.counts["model"]}/{self.call_limit.value()}')

    def drain(self):
        observer = self.observer
        if observer and observer.run_id == self.run_id:
            seq, frame = observer.latest(self.last_frame_seq)
            if frame is not None:
                # The observer retains only the latest frame. Never queue every frame.
                self.session.counts['captures'] += seq - self.last_frame_seq
                self.last_frame_seq = seq
                self.latest_frame = frame
                self.preview.set_image(frame)
            while True:
                try:
                    kind, payload = observer.events.get_nowait()
                except queue.Empty:
                    break
                if self.session.phase != 'active':
                    break
                if kind == 'ocr_status':
                    self.status.setText('本地 OCR 模型初始化中；屏幕预览仍继续更新。')
                    continue
                if kind == 'ocr_error':
                    msg = short(payload, 220)
                    self.status.setText('OCR 失败：' + msg + ' · 仍可点击「立即获取建议」')
                    if msg != self.ocr_error_notice:
                        self.append_message('system', '本地 OCR 异常：' + msg + '\\n画面捕获仍在运行；可直接尝试「立即获取建议」。')
                        self.ocr_error_notice = msg
                    continue
                if kind == 'error':
                    self.pause_observer()
                    self.append_message('system','本地识别停止：'+short(payload, 250))
                    break
                lines, scoped, icons = payload
                self.session.observe(lines, scoped=scoped)
                self.session.record_icons(icons)
                self.ocr_view.setPlainText(
                    self.session.latest_ocr or
                    f'本次 OCR 返回 {len(lines)} 行，可信文字 0 行。请检查框选区域、游戏窗口模式和文字大小。'
                )
                if not self.session.latest_ocr and not self.ocr_empty_notice:
                    self.ocr_empty_notice = True
                    self.append_message('system',
                        '本地 OCR 暂时没有可靠文字。可在「设置与校准」内框选血量、能量等具体区域，'
                        '或先点「立即获取建议」验证 AI。商店英雄头像需要单独的图标模板，OCR 无法直接读出。')
                if self.session.pending in ('health','energy','weapon','opponent') and self.session.current(self.session.pending) is not None:
                    self.session.skip_question()
                    self.reset_question()
                question = self.session.clarify()
                if question:
                    self.show_question(*question)
                self.maybe_model()
                if not lines:
                    self.status.setText('OCR 本轮未识别到文字 · 请校准 HUD 或点击「立即获取建议」')
                else:
                    self.status.setText(
                        f'OCR 本轮 {len(lines)} 行 / 可信 {len(self.session.latest_ocr.splitlines())} 行'
                    )
            self.refresh_state()
        while True:
            try:
                run, epoch, kind, data = self.model_results.get_nowait()
            except queue.Empty:
                break
            if run != self.run_id or epoch != self.model_epoch or self.session.phase != 'active':
                continue
            self.model_busy = False
            if kind == 'error':
                self.append_message('assistant','这次模型调用失败：'+short(data,220))
                self.status.setText('模型请求失败')
                continue
            model_kind, mode, result = data
            if model_kind == 'vision':
                self.session.match.apply(mode, result)
            action = short(result.get('action'), 350)
            if action:
                self.session.last_decision = action
            self.append_message('assistant', summarize_result(result),
                                f'{"视觉分析" if model_kind == "vision" else "OCR 文字建议"} · {time.strftime("%H:%M:%S")}')
            new_question = short(result.get('question'), 180)
            if new_question:
                extra = self.session.ask_extra(new_question)
                if extra:
                    self.show_question(*extra)
            self.status.setText('教练已更新建议 · '+time.strftime('%H:%M:%S'))
            self.refresh_state()
        if self.session.phase == 'active' and self.observer is None:
            self.refresh_state()  # Expired fields must not remain falsely current while paused.

    def closeEvent(self, event):
        if self.session.phase == 'active':
            if QMessageBox.question(self, '结束对局', '仍有进行中的对局。结束并保存摘要后退出？') != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.end_game()
        self.stop_observer()
        event.accept()


def main():
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(app.font())
    window = CoachWindow()
    window.show()
    return app.exec()