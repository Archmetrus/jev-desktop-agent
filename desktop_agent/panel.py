"""Native Qt control panel; the CLI and panel share one agent and one task queue."""
import json
import threading
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication,QDialog,QLabel,QVBoxLayout,QHBoxLayout,
    QComboBox,QPushButton,QLineEdit,QPlainTextEdit,QMessageBox)

from .config import ROOT
from .safety import display_command

_APP = None


class Panel(QDialog):
    def __init__(self, agent, features):
        super().__init__()
        self.agent,self.features=agent,features
        self.busy=False
        self.listening=False
        self.voice_stop=threading.Event()
        self.setWindowTitle('Jev kontrol paneli')
        self.resize(590,600)
        layout=QVBoxLayout(self);layout.setContentsMargins(22,18,22,18);layout.setSpacing(12)
        self.heading=QLabel('Jev');self.heading.setStyleSheet('font-size:24px;font-weight:600')
        layout.addWidget(self.heading)
        self.status=QLabel('Beklemede · mikrofon kapalı');layout.addWidget(self.status)
        row=QHBoxLayout();self.provider=QComboBox();self.provider.addItems(['laya','opencode','openrouter','typesafe'])
        self.provider.setCurrentText(agent.client.provider)
        self.device=QComboBox();self.device.addItems(['cpu','cuda']);self.device.setCurrentText(getattr(agent.client,'device','cpu'))
        self.apply=QPushButton('Seçimi uygula');self.apply.clicked.connect(self.change_client)
        row.addWidget(self.provider);row.addWidget(self.device);row.addWidget(self.apply);layout.addLayout(row)
        self.command=QLineEdit();self.command.setPlaceholderText('İngilizce komut: Pause music / Show targets')
        self.command.returnPressed.connect(self.submit);layout.addWidget(self.command)
        buttons=QHBoxLayout();self.execute=QPushButton('Uygula');self.execute.clicked.connect(self.submit)
        self.mic=QPushButton('Bas-konuş başlat');self.mic.clicked.connect(self.toggle_listen)
        self.stop=QPushButton('Durdur');self.stop.clicked.connect(self.stop_task)
        self.stop.setStyleSheet('color:#b42318;font-weight:600')
        for button in (self.execute,self.mic,self.stop): buttons.addWidget(button)
        layout.addLayout(buttons)
        self.heard=QLabel('Duyulan komut burada görünecek.');self.heard.setWordWrap(True)
        self.heard.setTextFormat(Qt.PlainText);layout.addWidget(self.heard)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);layout.addWidget(self.log)
        self.hint=QLabel('Ctrl+Alt+V: konuş · Ctrl+Alt+X: durdur\n/history: geçmiş · /features: tüm komutlar')
        layout.addWidget(self.hint)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(500)
        self.last_history=None
        self.refresh()

    def refresh(self):
        history=json.dumps(self.features.journal[-20:],ensure_ascii=False)
        if history!=self.last_history and not self.busy:
            self.last_history=history
            self.log.setPlainText('\n'.join(f"{r['action']} · {'tamam' if r['success'] else r.get('error','hata')}" for r in self.features.journal[-20:]))

    def stop_task(self):
        self.agent.cancel.set()
        self.voice_stop.set()
        self.status.setText('Durdurma istendi · sonraki adımlar iptal edilecek')

    def change_client(self):
        if self.busy or self.listening or getattr(self.agent,'_task_active',False): return
        from .cli import make_client
        from .laya_client import LayaClient
        from . import credentials
        provider=self.provider.currentText()
        previous=self.agent.client
        key=None
        if provider!='laya':
            key=previous.api_key if provider==previous.provider else credentials.lookup(provider)
            if not key:
                self.status.setText('Kayıtlı anahtar yok. CLI içinde /key ile anahtarı girin.');return
        new=make_client(provider,self.agent.config['request_timeout'],
                        self.agent.config['model'] if provider=='typesafe' else None,
                        self.device.currentText(),self.agent.config.get('laya',{}).get('threshold',.65))
        new.api_key=key
        self.agent.client=new
        if isinstance(previous,LayaClient): previous.close()
        previous.api_key=None
        self.status.setText(f'{provider} seçildi · mikrofon kapalı')

    def confirm(self, action):
        return QMessageBox.question(self,'İşlemi onayla',json.dumps(action,ensure_ascii=False),
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def perform(self, command):
        if self.busy: return {'success':False,'error':'TASK_BUSY'}
        self.busy=True;self.execute.setEnabled(False);self.apply.setEnabled(False)
        shown=display_command(command);self.heard.setText('Komut: '+shown)
        self.status.setText('Uygulanıyor')
        old=getattr(self.agent,'pump',None)
        def pump():
            QApplication.processEvents()
            if old: old()
        self.agent.pump=pump
        def event(name,data):
            if name in ('executing','result','uncertain'):
                self.log.appendPlainText(name+' · '+json.dumps(data,ensure_ascii=False))
        try:
            result=self.agent.process(command,on_event=event,confirm=self.confirm)
            self.status.setText('Tamamlandı' if result.get('success') else result.get('error','Hata'))
            return result
        finally:
            self.agent.pump=old;self.busy=False;self.execute.setEnabled(True);self.apply.setEnabled(True)

    def submit(self):
        if not self.listening and self.command.text().strip():
            command=self.command.text().strip();self.command.clear();self.perform(command)

    def toggle_listen(self):
        if getattr(self.agent,'voice_running',False) and not self.listening:
            self.status.setText('Bas-konuş zaten terminalden çalışıyor. Ctrl+Alt+V kullanın.');return
        if self.listening:
            self.stop_task();return
        from .speech import Speech
        from .shortcuts import hold_to_talk
        self.listening=True;self.voice_stop.clear();self.mic.setText('Dinlemeyi bitir');self.apply.setEnabled(False)
        try:
            hold_to_talk(Speech(self.agent.config.get('speech',{})),self.perform,
                self.agent.config.get('speech',{}).get('shortcut','CTRL+ALT+v'),
                agent=self.agent,stop_listening=self.voice_stop)
        except Exception as error:
            self.status.setText(getattr(error,'code','VOICE_START_FAILED'))
        finally:
            self.listening=False;self.mic.setText('Bas-konuş başlat');self.apply.setEnabled(True)

    def closeEvent(self,event):
        if self.busy or self.listening:
            self.stop_task();event.ignore()
        else:
            self.timer.stop();event.accept()


def show_panel(agent,features):
    global _APP
    _APP=QApplication.instance() or QApplication([])
    _APP.setQuitOnLastWindowClosed(False)
    panel=Panel(agent,features)
    panel.show()
    # Modal event loop also keeps the panel responsive during text-mode use.
    if not getattr(agent,'voice_running',False):
        panel.exec()
    return panel
