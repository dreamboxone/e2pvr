import os
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from E2PVR.core import CueScheduler, split_cues
from E2PVR.live import setup


def cue(start, text, final=True):
    return dict(start=start, end=start+2000, text=text, final=final)


class TimingTests(unittest.TestCase):
    def test_preview_never_rewrites_committed_text(self):
        scheduler = CueScheduler()
        self.assertEqual(scheduler.refresh([cue(0, "incomplete", False)], 0), "")
        self.assertEqual(scheduler.refresh([cue(0, "complete")], 200), "complete")

    def test_reading_floor_and_pause(self):
        scheduler = CueScheduler()
        first, second = cue(0, "first\nline"), cue(100, "second")
        self.assertEqual(scheduler.refresh([first], 0), "first\nline")
        for position in (100, 100, 1900):
            self.assertEqual(scheduler.refresh([first, second], position), "first\nline")
        self.assertEqual(scheduler.refresh([first, second], 2000), "second")

    def test_old_captions_not_resurrected_and_seek_resets(self):
        scheduler = CueScheduler()
        self.assertEqual(scheduler.refresh([cue(0, "old")], 5000), "")
        scheduler.reset()
        self.assertEqual(scheduler.refresh([cue(0, "old")], 0), "old")

    def test_future_and_manual_correction(self):
        scheduler = CueScheduler()
        self.assertEqual(scheduler.refresh([cue(1000, "future")], 0, 500), "")
        self.assertEqual(scheduler.refresh([cue(1000, "future")], 1499, 500), "")
        self.assertEqual(scheduler.refresh([cue(1000, "future")], 1500, 500), "future")

    def test_two_short_phrases_keep_order(self):
        scheduler = CueScheduler()
        self.assertEqual(scheduler.refresh([cue(0,"first"),cue(100,"second")], 200), "first\nsecond")

    def test_splitting_never_loses_words_or_exceeds_two_lines(self):
        text = " ".join("word%d" % index for index in range(60))
        items = split_cues([dict(start=0, end=12000, text=text)], 24)
        reconstructed = " ".join(" ".join(item["text"].split()) for item in items)
        self.assertEqual(reconstructed, text)
        self.assertEqual(items[0]["start"], 0)
        self.assertEqual(items[-1]["end"], 12000)
        for item in items:
            self.assertLessEqual(len(item["text"].splitlines()), 2)
            self.assertTrue(all(len(line) <= 24 for line in item["text"].splitlines()))

    def test_live_setup_requests_only_text(self):
        value = setup("ar")["setup"]
        self.assertEqual(value["generationConfig"]["responseModalities"], ["TEXT"])
        self.assertTrue(value["generationConfig"]["translationConfig"]["echoTargetLanguage"])
        self.assertIn("inputAudioTranscription", value)
        self.assertIn("outputAudioTranscription", value)
        self.assertNotIn("speechConfig", value["generationConfig"])
        self.assertEqual(setup("fa", "resume-handle")["setup"]["sessionResumption"], {"handle": "resume-handle"})


if __name__ == "__main__":
    unittest.main()
