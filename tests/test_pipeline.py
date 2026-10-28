import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from audiobook import AudiobookConverter, ConversionError
from audiobook.engines import BaseEngine
from audiobook.processor import chunk_text, clean_text, split_chapters

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "sample_book.txt")


class FakeEngine(BaseEngine):
    """Offline stand-in: writes a tone whose length follows the text length."""
    name = "fake"; file_ext = ".wav"; calls = 0
    def synthesize(self, text, out_path):
        from pydub.generators import Sine
        FakeEngine.calls += 1
        Sine(440).to_audio_segment(duration=len(text) * 20).export(out_path, format="wav")


class Flaky(FakeEngine):
    def __init__(self): self.n = 0
    def synthesize(self, text, out_path):
        self.n += 1
        if self.n == 1: raise RuntimeError("temporary failure")
        super().synthesize(text, out_path)


class T(unittest.TestCase):
    def test_chunking_limit(self):
        txt = ("Hello world. " * 400) + "\n\n" + ("x" * 5000)
        for c in chunk_text(txt, 500):
            self.assertLessEqual(len(c), 500)

    def test_clean(self):
        self.assertEqual(clean_text("exam-\nple  line\nnext"), "example line next")

    def test_chapters(self):
        self.assertEqual(len(split_chapters(open(SAMPLE).read())), 3)

    def run_conv(self, eng, out, **kw):
        d = tempfile.mkdtemp()
        return AudiobookConverter(eng, log=lambda m: None, pause_ms=50,
                                  cache_dir=os.path.join(d, "c"), **kw).convert(
            kw.pop("src", SAMPLE), os.path.join(d, out), "Test", "Me"), d

    def test_mp3_with_chapters(self):
        r, d = self.run_conv(FakeEngine(), "o.mp3")
        self.assertEqual(len(r["chapters"]), 3)
        from mutagen.mp3 import MP3
        m = MP3(os.path.join(d, "o.mp3"))
        self.assertGreater(m.info.length, 1)
        self.assertEqual(str(m.tags["TIT2"]), "Test")
        self.assertEqual(len([k for k in m.tags if k.startswith("CHAP")]), 3)
        self.assertTrue(os.path.exists(os.path.join(d, "o.chapters.txt")))

    def test_wav_and_retry(self):
        r, _ = self.run_conv(Flaky(), "o.wav")
        self.assertGreater(r["duration_ms"], 1000)

    def test_cache(self):
        d = tempfile.mkdtemp(); FakeEngine.calls = 0
        mk = lambda: AudiobookConverter(FakeEngine(), log=lambda m: None,
                                        cache_dir=os.path.join(d, "c"))
        mk().convert(SAMPLE, os.path.join(d, "a.mp3")); first = FakeEngine.calls
        mk().convert(SAMPLE, os.path.join(d, "b.mp3"))
        self.assertEqual(FakeEngine.calls, first)

    def test_errors(self):
        d = tempfile.mkdtemp()
        e = os.path.join(d, "empty.txt"); open(e, "w").write("   ")
        conv = AudiobookConverter(FakeEngine(), log=lambda m: None)
        for bad in (e, os.path.join(d, "nope.pdf")):
            with self.assertRaises(ConversionError):
                conv.convert(bad, os.path.join(d, "x.mp3"))

    def test_pdf(self):
        from reportlab.pdfgen import canvas
        d = tempfile.mkdtemp(); p = os.path.join(d, "b.pdf")
        c = canvas.Canvas(p)
        for i in range(2):
            c.drawString(72, 750, f"Page {i+1}. Python makes audiobooks easy."); c.showPage()
        c.save()
        r = AudiobookConverter(FakeEngine(), log=lambda m: None).convert(
            p, os.path.join(d, "b.mp3")); self.assertGreater(r["duration_ms"], 500)


if __name__ == "__main__":
    unittest.main()
