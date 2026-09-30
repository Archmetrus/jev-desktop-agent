import io
import struct
import threading
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from desktop_agent.speech import Speech, voice_loop


class SpeechTests(unittest.TestCase):
    def test_energy_detects_signal_and_silence(self):
        self.assertEqual(Speech.rms(b'\x00' * 100), 0)
        self.assertAlmostEqual(Speech.rms(struct.pack('<hhh', 16384, -16384, 16384)), 0.5)

    @patch("desktop_agent.speech.subprocess.run")
    def test_microphone_limit_never_raises_a_lower_volume(self, run):
        speech = Speech({})
        run.return_value.stdout = "Volume: 0.10"
        self.assertEqual(speech.cap_microphone(), 0.10)
        self.assertEqual(run.call_count, 1)
        run.reset_mock()
        run.return_value.stdout = "Volume: 0.80"
        self.assertEqual(speech.cap_microphone(), 0.25)
        self.assertEqual(run.call_args.args[0],
                         ["wpctl", "set-volume", "--limit", "0.25", "@DEFAULT_AUDIO_SOURCE@", "0.25"])

    def test_wake_mode_discards_unaddressed_speech(self):
        speech = Mock()
        speech.recognize.side_effect = ["Open Firefox", "Hey Jev, Open Firefox", "Jev stop listening"]
        callback = Mock()
        with redirect_stdout(io.StringIO()):
            voice_loop(Mock(), speech, "wake", callback)
        callback.assert_called_once_with("Open Firefox")

    def test_no_capture_when_whisper_is_missing(self):
        speech = Speech({"binary": "/does/not/exist", "model": "/missing"})
        with patch.object(speech, "capture") as capture:
            with self.assertRaisesRegex(Exception, "WHISPER_NOT_INSTALLED"):
                speech.recognize()
            capture.assert_not_called()

    @patch("desktop_agent.speech.subprocess.Popen")
    def test_release_stops_capture_and_closes_recorder(self, popen):
        speech = Speech({})
        stop = threading.Event()
        stop.set()
        with patch.object(speech, "cap_microphone", return_value=0.25):
            with self.assertRaisesRegex(Exception, "NO_SPEECH_DETECTED"):
                speech.capture(lambda message: None, stop_event=stop)
        popen.return_value.terminate.assert_called_once()
        popen.return_value.stdout.read1.assert_not_called()
        popen.return_value.stdout.close.assert_called_once()

    @patch("desktop_agent.speech.subprocess.Popen")
    def test_cancel_kills_local_transcription_process(self, popen):
        process = popen.return_value
        process.poll.return_value = None
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(Exception, "CANCELLED"):
            Speech.run_local(["whisper-cli"], 60, cancel)
        process.kill.assert_called_once()
        process.wait.assert_called_once()

    @patch("desktop_agent.speech.subprocess.Popen")
    @patch("desktop_agent.speech.select.select")
    @patch("desktop_agent.speech.time.monotonic", side_effect=[0, 0.1, 0.2, 10, 10.1, 10.2])
    def test_hold_does_not_end_on_silence(self, clock, select_mock, popen):
        speech = Speech({})
        stop = threading.Event()
        voiced = struct.pack('<h', 16384) * 4800
        chunks = [voiced, bytes(3200), bytes(3200)]
        def read(size):
            chunk = chunks.pop(0)
            if not chunks:
                stop.set()
            return chunk
        popen.return_value.stdout.read1.side_effect = read
        select_mock.return_value = ([popen.return_value.stdout], [], [])
        with patch.object(speech, "cap_microphone", return_value=0.25):
            raw = speech.capture(lambda text: None, stop_event=stop)
        self.assertEqual(len(raw), len(voiced) + 6400)
        self.assertEqual(popen.return_value.stdout.read1.call_count, 3)
