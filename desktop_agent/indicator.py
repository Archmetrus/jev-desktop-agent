"""Small, unfocused status window for hold-to-talk on KDE Wayland."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class Indicator(QWidget):
    changed = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jev ses durumu")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        self.title = QLabel()
        self.details = QLabel()
        self.details.setTextFormat(Qt.PlainText)
        self.title.setTextFormat(Qt.PlainText)
        self.details.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.details)
        self.changed.connect(self.update_status)
        self.update_status("Beklemede", "Ctrl+Alt+V basılı tutarak konuş")

    def update_status(self, status, details):
        colors = {"Beklemede": "#64748b", "Kayıt": "#ef4444", "Çözümleniyor": "#eab308",
                  "Uygulanıyor": "#38bdf8", "Hata": "#fb923c"}
        self.setStyleSheet("QWidget { background: #111827; color: #e5e7eb; border-radius: 12px; }"
                           "QLabel { background: transparent; font-size: 13px; }" )
        self.title.setStyleSheet(f"color: {colors.get(status, '#64748b')}; font-size: 16px; font-weight: 600;")
        self.title.setText("Jev · " + status)
        self.details.setText(details[:300])
        self.adjustSize()


def create_indicator():
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    widget = Indicator()
    widget.show()
    application.processEvents()
    return application, widget
