import os
import subprocess
import sys
import time
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from E2PVR.worker import stop_process, merge_text


class WorkerTests(unittest.TestCase):
    def test_blocked_audio_producer_is_reaped_without_waiting_for_pipe_flush(self):
        code = "import os,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); os.write(1,b'ready\\n'); exec('while True: os.write(1,b\"x\"*65536)')"
        process = subprocess.Popen([sys.executable,"-u","-c",code],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        try:
            self.assertEqual(process.stdout.readline(),b"ready\n")
            started=time.monotonic()
            stop_process(process)
            self.assertIsNotNone(process.returncode)
            self.assertLess(time.monotonic()-started,2)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_cumulative_and_delta_transcript_updates_do_not_repeat_text(self):
        text=merge_text("", "Hello")
        text=merge_text(text, "Hello world")
        self.assertEqual(merge_text(text,"world"),"Hello world")
        self.assertEqual(merge_text(text,"."),"Hello world.")


if __name__ == "__main__":
    unittest.main()
