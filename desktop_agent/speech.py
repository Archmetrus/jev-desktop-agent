"""Local PipeWire capture and whisper.cpp transcription; never downloads files."""
import array
import json
import math
import re
import select
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from .client import AgentError
from .config import ROOT
from .safety import display_command


class Speech:
    RATE = 16000

    def __init__(self, config):
        self.config = config

    def check(self):
        for tool in ("parec", "wpctl"):
            if not shutil.which(tool):
                raise AgentError("AUDIO_TOOL_MISSING")
        binary = self.config.get("binary", "whisper-cli")
        if "/" in binary and not Path(binary).is_absolute():
            binary = str(ROOT / binary)
        if not shutil.which(binary):
            raise AgentError("WHISPER_NOT_INSTALLED")
        model = Path(self.config.get("model", ""))
        if not model.is_absolute():
            model = ROOT / model
        if not model.is_file():
            raise AgentError("SPEECH_MODEL_MISSING")
        return binary, model

    def cap_microphone(self):
        try:
            result = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"],
                capture_output=True, text=True, timeout=5, check=True)
            match = re.search(r"Volume:\s*([0-9.]+)", result.stdout)
            if not match:
                raise AgentError("MICROPHONE_UNAVAILABLE")
            if "MUTED" in result.stdout:
                raise AgentError("MICROPHONE_MUTED")
            volume = float(match.group(1))
            if volume > 0.25:
                subprocess.run(["wpctl", "set-volume", "--limit", "0.25",
                                "@DEFAULT_AUDIO_SOURCE@", "0.25"],
                               capture_output=True, timeout=5, check=True)
            return min(volume, 0.25)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise AgentError("MICROPHONE_UNAVAILABLE") from None

    @staticmethod
    def rms(raw):
        samples = array.array("h")
        samples.frombytes(raw[:len(raw) // 2 * 2])
        if not samples:
            return 0.0
        return math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768

    def capture(self, on_status=print, stop_event=None, cancel_event=None):
        volume = self.cap_microphone()
        on_status(f"[MIC] Seviye %{volume * 100:.0f} · konuşmanı bekliyorum…")
        process = subprocess.Popen(["parec", "--raw", "--format=s16le", "--rate=16000",
                                    "--channels=1", "--latency-msec=50"],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw = bytearray()
        started = time.monotonic()
        last_voice = None
        voiced_seconds = 0.0
        threshold = self.config.get("energy_threshold", 0.004)
        try:
            while time.monotonic() - started < self.config.get("max_record_seconds", 20):
                if cancel_event is not None and cancel_event.is_set():
                    raise AgentError("CANCELLED")
                if stop_event is not None and stop_event.is_set():
                    break
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                if not ready:
                    if process.poll() is not None:
                        raise AgentError("MICROPHONE_CAPTURE_FAILED")
                    continue
                chunk = process.stdout.read1(3200)
                if not chunk:
                    raise AgentError("MICROPHONE_CAPTURE_FAILED")
                raw.extend(chunk)
                if self.rms(chunk) >= threshold:
                    if last_voice is None:
                        on_status("[MIC] Ses algılandı; " +
                                  ("kısayolu bırakınca çözümlenecek." if stop_event is not None
                                   else "konuşma bitince çözümlenecek."))
                    last_voice = time.monotonic()
                    voiced_seconds += len(chunk) / (2 * self.RATE)
                if stop_event is None and last_voice is not None and time.monotonic() - last_voice >= self.config.get("silence_seconds", 1.3):
                    break
            else:
                if stop_event is not None:
                    raise AgentError("RECORDING_TOO_LONG")
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()
        if voiced_seconds < 0.25:
            raise AgentError("NO_SPEECH_DETECTED")
        return bytes(raw[:len(raw) // 2 * 2])

    @staticmethod
    def run_local(argv, timeout, cancel_event=None):
        process = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    raise AgentError("CANCELLED")
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(argv[0], timeout)
                time.sleep(0.05)
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, argv[0])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def recognize(self, on_status=print, stop_event=None, cancel_event=None):
        binary, model = self.check()
        raw = self.capture(on_status, stop_event, cancel_event)
        on_status("[STT] İngilizce konuşma yerel olarak çözümleniyor…")
        with tempfile.TemporaryDirectory(prefix="jev-speech-") as directory:
            audio = Path(directory) / "command.wav"
            output = Path(directory) / "transcript"
            with wave.open(str(audio), "wb") as file:
                file.setnchannels(1)
                file.setsampwidth(2)
                file.setframerate(self.RATE)
                file.writeframes(raw)
            try:
                if self.config.get("denoise", True):
                    if not shutil.which("ffmpeg"):
                        raise AgentError("DENOISE_TOOL_MISSING")
                    clean = Path(directory) / "clean.wav"
                    self.run_local(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                    "-i", str(audio), "-af",
                                    "highpass=f=80,afftdn=nr=12:nf=-35:tn=1",
                                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(clean)],
                                   10, cancel_event)
                    audio = clean
                    on_status("[STT] Fan/arka plan gürültüsü için filtre uygulandı.")
                argv = [binary, "-m", str(model), "-f", str(audio), "-l", "en",
                        "-nt", "-otxt", "-of", str(output)]
                vocabulary = self.config.get("vocabulary", [])
                if vocabulary:
                    argv.extend(["--prompt", ", ".join(vocabulary)])
                self.run_local(argv, 60, cancel_event)
                text = output.with_suffix(".txt").read_text().strip()
            except subprocess.TimeoutExpired:
                raise AgentError("TRANSCRIPTION_TIMEOUT") from None
            except (OSError, subprocess.SubprocessError):
                raise AgentError("TRANSCRIPTION_FAILED") from None
        if not text or re.fullmatch(r"[\[\(].*[\]\)]", text):
            raise AgentError("NO_SPEECH_DETECTED")
        return text


def voice_loop(agent, speech, mode="ptt", on_result=None):
    speech.check()
    print(f"[VOICE] Mod: {mode}. Ctrl+C dinlemeyi durdurur. Eylem sırasında kayıt yapılmaz.")
    try:
        while True:
            if mode == "ptt":
                input("[MIC] Kayıt için Enter; bitirmek için Ctrl+C: ")
            try:
                text = speech.recognize()
            except AgentError as error:
                if error.code == "NO_SPEECH_DETECTED":
                    print("[MIC] Konuşma algılanmadı.")
                    continue
                raise
            if mode == "wake":
                match = re.match(r"^\s*(?:hey\s+)?(?:jev|jeff|jef)[\s,:.!-]+(.+)$", text, re.I)
                if not match:
                    print("[VOICE] Uyandırma kelimesi yok; komut gönderilmedi.")
                    continue
                text = match.group(1).strip()
            print("[STT] " + json.dumps(display_command(text), ensure_ascii=False))
            if text.lower().strip(" .!") in ("stop listening", "stop jev"):
                break
            if on_result:
                on_result(text)
            else:
                print(agent.process(text))
    except (KeyboardInterrupt, EOFError):
        print("\n[VOICE] Dinleme durdu.")
