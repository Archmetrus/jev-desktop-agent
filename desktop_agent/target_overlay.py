"""A non-focusing numbered target legend (works with KDE Wayland)."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

_APP = None


def show_targets(items):
    global _APP
    _APP = QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    widget = QWidget()
    widget.setWindowTitle('Jev hedefleri')
    widget.setWindowFlags(Qt.ToolTip|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus)
    widget.setAttribute(Qt.WA_TransparentForMouseEvents)
    widget.setAttribute(Qt.WA_ShowWithoutActivating)
    layout=QVBoxLayout(widget)
    heading=QLabel('Hedef numarasını söyle: Click number two')
    layout.addWidget(heading)
    scroll=QScrollArea();scroll.setWidgetResizable(True)
    body=QWidget();rows=QVBoxLayout(body)
    for i,item in enumerate(items):
        label=QLabel(f"{i+1}   {item.get('label') or item.get('role','Hedef')}")
        label.setTextFormat(Qt.PlainText);label.setWordWrap(True);rows.addWidget(label)
    rows.addStretch();scroll.setWidget(body);layout.addWidget(scroll)
    widget.resize(380, min(620,max(180,80+len(items)*32)))
    widget.show();_APP.processEvents()
    QTimer.singleShot(30000,widget.close)
    return widget
