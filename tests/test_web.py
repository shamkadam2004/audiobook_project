import io, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A
REAL_TRANSLATE = A.translate_text


class Web(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        A.translate_text = lambda t, l: "[" + l + "] " + t
        A.synthesize_mp3 = lambda t, l: b"ID3fakeaudio"

    def up(self, name, data):
        return self.c.post("/api/extract", data={"file": (io.BytesIO(data), name)})

    def test_page(self):
        self.assertIn(b"Your notes,", self.c.get("/").data)

    def test_txt_and_pdf(self):
        r = self.up("a.txt", b"Hello world."); self.assertEqual(r.json["text"], "Hello world.")
        from reportlab.pdfgen import canvas
        b = io.BytesIO(); cv = canvas.Canvas(b); cv.drawString(72, 750, "PDF text here"); cv.save()
        self.assertIn("PDF text here", self.up("a.pdf", b.getvalue()).json["text"])

    def test_errors(self):
        self.assertEqual(self.up("a.exe", b"x").status_code, 400)
        self.assertEqual(self.up("e.txt", b"  ").status_code, 422)
        self.assertEqual(self.c.post("/api/extract").status_code, 400)

    def test_translate_tts(self):
        j = {"text": "Hi", "lang": "hi"}
        self.assertEqual(self.c.post("/api/translate", json=j).json["text"], "[hi] Hi")
        self.assertEqual(self.c.post("/api/translate", json={"text": "Hi", "lang": "en"}).json["text"], "Hi")
        self.assertEqual(self.c.post("/api/tts", json=j).mimetype, "audio/mpeg")
        self.assertEqual(self.c.post("/api/tts", json={"text": "x", "lang": "xx"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()


class Fallback(unittest.TestCase):
    def setUp(self):
        import time
        self._sleep, time.sleep = time.sleep, lambda s: None
        self._prov = list(A.PROVIDERS)

    def tearDown(self):
        import time
        time.sleep = self._sleep; A.PROVIDERS[:] = self._prov

    def test_falls_back_to_next_route(self):
        def dead(p, l): raise ConnectionError("blocked")
        def ok(p, l): return "T" + p[:3]
        A.PROVIDERS[:] = [("a", dead, 1500), ("b", ok, 1500)]
        out = REAL_TRANSLATE("This is a sentence. " * 300, "mr")
        self.assertTrue(out.startswith("T"))

    def test_retries_same_route(self):
        n = {"c": 0}
        def flaky(p, l):
            n["c"] += 1
            if n["c"] == 1: raise ConnectionError("drop")
            return "ok"
        A.PROVIDERS[:] = [("a", flaky, 1500)]
        self.assertEqual(REAL_TRANSLATE("Hello there.", "hi"), "ok")

    def test_all_fail_message(self):
        def dead(p, l): raise ConnectionError("blocked")
        A.PROVIDERS[:] = [("a", dead, 1500), ("b", dead, 450)]
        with self.assertRaises(RuntimeError) as c:
            REAL_TRANSLATE("Hello.", "hi")
        self.assertIn("a (ConnectionError", str(c.exception))

    def test_pieces_respect_size(self):
        seen = []
        A.PROVIDERS[:] = [("m", lambda p, l: seen.append(len(p)) or "x", 450)]
        REAL_TRANSLATE("Short sentence here. " * 200, "hi")
        self.assertLessEqual(max(seen), 450); self.assertGreater(len(seen), 5)


if __name__ == "__main__":
    unittest.main()
