"""Small, presentation-only Qt widgets for the Coach desktop app."""
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
    QSizePolicy,
)


class GamePreview(QWidget):
    """Live screenshot with read-only, always-labelled state overlays."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(290)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image = QPixmap()
        self.facts = {'health': '—', 'energy': '—', 'round': '—', 'weapon': '—'}
        self.shop = ['未知'] * 5

    def set_image(self, image):
        if image is None:
            self.image = QPixmap()
            self.update()
            return
        rgb = image.convert('RGB')
        raw = rgb.tobytes()
        qimage = QImage(raw, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888)
        self.image = QPixmap.fromImage(qimage.copy())
        self.update()

    def set_state(self, facts, shop):
        self.facts = dict(facts)
        self.shop = list(shop)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#111823'))
        inner = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        if self.image.isNull():
            painter.setPen(QColor('#8491A3'))
            painter.setFont(QFont('Microsoft YaHei UI', 12))
            painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, '等待游戏画面\n选择区域并点击「开始本局」')
            return
        size = self.image.size().scaled(inner.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
        area = QRectF(inner.center().x()-size.width()/2, inner.center().y()-size.height()/2,
                      size.width(), size.height())
        painter.drawPixmap(area.toRect(), self.image)
        # Paint semitransparent overlays on the preview, never on the captured image.
        fields = [('HP', 'health'), ('能量', 'energy'), ('回合', 'round'), ('武器', 'weapon')]
        x, y = area.x()+12, area.y()+12
        block_width = min(340., max(240., area.width()-24))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(13, 20, 34, 217))
        painter.drawRoundedRect(QRectF(x, y, block_width, 43), 10, 10)
        painter.setFont(QFont('Microsoft YaHei UI', 9, QFont.Weight.DemiBold))
        for i, (label, key) in enumerate(fields):
            cx = x + 14 + i * (block_width-24)/4
            painter.setPen(QColor('#8DA6BE'))
            painter.drawText(QRectF(cx, y+5, 79, 14), Qt.AlignmentFlag.AlignLeft, label)
            painter.setPen(QColor('#F7FAFF'))
            painter.drawText(QRectF(cx, y+20, 79, 18), Qt.AlignmentFlag.AlignLeft, str(self.facts.get(key) or '未知')[:7])
        if area.height() >= 130:
            bar = QRectF(area.x()+12, area.bottom()-54, max(30, area.width()-24), 42)
            painter.setBrush(QColor(13, 20, 34, 217))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar, 10, 10)
            painter.setPen(QColor('#E7ECF4'))
            label = '商店 · ' + '   /   '.join(str(x)[:6] for x in self.shop)
            painter.drawText(bar.adjusted(14, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(bar.width()-28)))


class RegionPicker(QDialog):
    """Pick screen rectangle, using one explicit user gesture."""
    def __init__(self, parent, source, capture):
        super().__init__(parent)
        self.setWindowTitle('框选屏幕区域 · Esc 取消')
        self.setModal(True)
        self.source = dict(source)
        image = capture(source)
        rgb = image.convert('RGB')
        raw = rgb.tobytes()
        qimage = QImage(raw, rgb.width, rgb.height, rgb.width*3, QImage.Format.Format_RGB888)
        self.original = QPixmap.fromImage(qimage.copy())
        self.factor = min(1., 1240 / rgb.width, 760 / rgb.height)
        self.setFixedSize(round(rgb.width*self.factor), round(rgb.height*self.factor))
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.anchor = None
        self.current = None
        self.selection = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(self.rect(), self.original)
        p.fillRect(self.rect(), QColor(0, 0, 0, 50))
        if self.anchor and self.current:
            rect = QRect(self.anchor, self.current).normalized()
            p.setBrush(QColor(58, 152, 245, 35))
            p.setPen(QPen(QColor('#56B4FF'), 2))
            p.drawRect(rect)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.anchor = e.position().toPoint()
            self.current = self.anchor

    def mouseMoveEvent(self, e):
        if self.anchor:
            self.current = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.anchor and e.button() == Qt.MouseButton.LeftButton:
            rect = QRect(self.anchor, e.position().toPoint()).normalized().intersected(self.rect())
            if rect.width() >= 12 and rect.height() >= 12:
                self.selection = {
                    'left': self.source['left'] + round(rect.left()/self.factor),
                    'top': self.source['top'] + round(rect.top()/self.factor),
                    'width': round(rect.width()/self.factor),
                    'height': round(rect.height()/self.factor),
                }
                self.accept()
            else:
                self.anchor = None
                self.update()


class ChatFeed(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName('ChatFeed')
        body = QWidget()
        body.setObjectName('ChatSurface')
        self.layout_messages = QVBoxLayout(body)
        self.layout_messages.setContentsMargins(18, 22, 18, 22)
        self.layout_messages.setSpacing(18)
        self.layout_messages.addStretch()
        self.setWidget(body)
        self.history = []

    def clear_messages(self):
        while self.layout_messages.count() > 1:
            item = self.layout_messages.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.history.clear()

    def append(self, role, content, note=''):
        content = str(content).strip()
        if not content:
            return
        self.history.append((role, content))
        wrap = QWidget()
        wrap.setObjectName('ChatSurface')
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        if role == 'user':
            row.addStretch(1)
        bubble = QFrame()
        bubble.setObjectName('UserBubble' if role == 'user' else ('SystemBubble' if role == 'system' else 'AssistantBubble'))
        bubble.setMaximumWidth(500)
        col = QVBoxLayout(bubble)
        col.setContentsMargins(15, 12, 15, 13)
        col.setSpacing(6)
        head = QLabel({'assistant':'COACH','user':'你','system':'系统'}.get(role,'COACH'))
        head.setObjectName('ChatSpeaker')
        col.addWidget(head)
        label = QLabel(content)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName('ChatBody')
        col.addWidget(label)
        if note:
            foot = QLabel(note)
            foot.setObjectName('ChatNote')
            foot.setTextFormat(Qt.TextFormat.PlainText)
            foot.setWordWrap(True)
            col.addWidget(foot)
        row.addWidget(bubble, 0)
        if role != 'user':
            row.addStretch(1)
        self.layout_messages.insertWidget(self.layout_messages.count()-1, wrap)
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()))