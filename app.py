"""AudioBook web app (Flask backend).   Run:  python app.py   ->  http://127.0.0.1:5000"""
import io
import os
import shutil
import tempfile

from flask import Flask, jsonify, render_template, request, send_file

from audiobook.extractor import ExtractionError, extract_text
from audiobook.processor import chunk_text, clean_text

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB uploads

LANGS = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}


# ---------- service functions (kept separate so they are easy to test) ----------
def ocr_image(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise ExtractionError("OCR needs:  pip install pytesseract Pillow") from e
    if not shutil.which("tesseract"):
        for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break
        else:
            raise ExtractionError(
                "Tesseract OCR is not installed. Install it (see README) to read images.")
    try:
        text = pytesseract.image_to_string(Image.open(path))
    except Exception as e:
        raise ExtractionError(f"Could not read the image: {e}") from e
    if not text.strip():
        raise ExtractionError("No text could be recognised in the image.")
    return text


def _gtx(piece: str, lang: str) -> str:
    """Google's public web endpoint, called directly (most tolerant route)."""
    import requests
    r = requests.post("https://translate.googleapis.com/translate_a/single",
                      params={"client": "gtx", "sl": "auto", "tl": lang, "dt": "t"},
                      data={"q": piece}, timeout=20,
                      headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return "".join(seg[0] for seg in r.json()[0] if seg and seg[0])


def _deep_google(piece: str, lang: str) -> str:
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source="auto", target=lang).translate(piece) or ""


def _mymemory(piece: str, lang: str) -> str:
    from deep_translator import MyMemoryTranslator
    return MyMemoryTranslator(source="en-GB", target={"hi": "hi-IN", "mr": "mr-IN"}[lang]).translate(piece) or ""


# (name, function, max characters per request)
PROVIDERS = [("google", _gtx, 1500), ("google-2", _deep_google, 1500), ("mymemory", _mymemory, 450)]


def translate_text(text: str, lang: str) -> str:
    """Try several translation routes; fall back automatically if one is blocked."""
    import time
    errors = {}
    for name, fn, size in PROVIDERS:
        try:
            out = []
            for piece in chunk_text(text, size):
                for attempt in range(3):
                    try:
                        out.append(fn(piece, lang))
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise
                        time.sleep(1.5 * (attempt + 1))
                time.sleep(0.4)
            return "\n\n".join(out)
        except Exception as e:
            errors[name] = f"{type(e).__name__}: {str(e)[:120]}"
    raise RuntimeError("all translation routes failed - " +
                       "; ".join(f"{k} ({v})" for k, v in errors.items()))


def synthesize_mp3(text: str, lang: str) -> bytes:
    from gtts import gTTS
    buf = io.BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(buf)
    return buf.getvalue()


# ---------- routes ----------
@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/extract")
def api_extract():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="No file uploaded."), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in IMAGE_EXT | {".pdf", ".txt"}:
        return jsonify(error="Please upload a PDF, PNG or JPG file."), 400
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "upload" + ext)
    try:
        f.save(path)
        text = ocr_image(path) if ext in IMAGE_EXT else extract_text(path)
        return jsonify(text=clean_text(text))
    except ExtractionError as e:
        return jsonify(error=str(e)), 422
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.post("/api/translate")
def api_translate():
    d = request.get_json(silent=True) or {}
    text, lang = (d.get("text") or "").strip(), d.get("lang")
    if not text or lang not in LANGS:
        return jsonify(error="Text and a valid language are required."), 400
    if lang == "en":
        return jsonify(text=text)
    try:
        return jsonify(text=translate_text(text, lang))
    except Exception as e:
        return jsonify(error=f"Translation failed: {e}"), 502


@app.post("/api/tts")
def api_tts():
    d = request.get_json(silent=True) or {}
    text, lang = (d.get("text") or "").strip(), d.get("lang")
    if not text or lang not in LANGS:
        return jsonify(error="Text and a valid language are required."), 400
    try:
        audio = synthesize_mp3(text[:3000], lang)
    except Exception as e:
        return jsonify(error=f"Speech failed (check internet): {e}"), 502
    return send_file(io.BytesIO(audio), mimetype="audio/mpeg")


def find_port(start: int = 5000) -> int:
    import socket
    for port in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 0)) or find_port()
    print(f"\n  AudioBook is running.  Open this in your browser:  http://127.0.0.1:{port}\n"
          "  (press Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=port, debug=False)
