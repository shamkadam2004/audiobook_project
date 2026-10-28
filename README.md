# Audio Book Using Python

## Website - run in VS Code
**Easiest (Windows):** double-click **run.bat**. It installs the libraries and starts the site.

**Or from the VS Code terminal** (open the folder that contains `app.py` first):
```
pip install -r requirements.txt
python app.py
```
The terminal prints a link such as **http://127.0.0.1:5000** - Ctrl+click it (or paste it in your browser).
Stop the site with Ctrl+C.

Features: upload PDF/PNG/JPG, extracted text box, English / Hindi / Marathi translation,
audio player (play, stop, 1x-5x speed, volume, progress) and bookmarks (saved in your browser).
Needs internet (Google Translate + Google voice via gTTS).

**Reading images (OCR, optional):** install Tesseract once -  `winget install UB-Mannheim.TesseractOCR`
(then restart VS Code). PDFs and typed text work without it. Handwriting is recognised only roughly.

Tests: `python -m unittest discover -s tests`

---
## Desktop / command-line version

Converts a **PDF or TXT** file into an **MP3/WAV audiobook** with chapter markers and metadata.
Implements the workflow from the project presentation:

`PDF/Text Input → Text Extraction (PyPDF2) → Text Processing (clean + chunk) → Speech Synthesis (pyttsx3 / gTTS) → Audio Processing (pydub) → Output MP3/WAV`

## Setup
1. Install Python 3.9+ and **FFmpeg** (required by pydub)
   - Windows: `winget install ffmpeg` (or download from ffmpeg.org and add `bin` to PATH)
   - macOS: `brew install ffmpeg`  |  Linux: `sudo apt install ffmpeg espeak-ng`
2. `pip install -r requirements-desktop.txt`
3. Tkinter ships with Python on Windows/macOS (Linux: `sudo apt install python3-tk`).

## Run
**GUI:** `python gui.py`

**Command line:**
```
python -m audiobook samples/sample_book.txt -o book.mp3 --title "My Book" --author "Me"
python -m audiobook mybook.pdf -e pyttsx3 --rate 160 -o mybook.wav     # offline
python -m audiobook mybook.pdf -l hi --pages 1-20                        # Hindi, pages 1-20
python -m audiobook --list-voices                                        # pyttsx3 voices
```
| Engine | Internet | Quality | Output |
|---|---|---|---|
| gtts | needed | natural, 30+ languages | .mp3 |
| pyttsx3 | not needed | system voices | .wav → exported |

## Design considerations (from slide 7)
- **Chunking** – text split at sentence boundaries (`--chunk`, default 1500 chars) to avoid buffer/time limits.
- **Caching** – each synthesized chunk is cached in `.audiobook_cache/`; re-runs and resumed runs skip finished chunks.
- **Error handling** – empty/scanned pages skipped, several text encodings tried, encrypted PDFs reported, TTS retried 3×.
- **Metadata** – title/author/genre ID3 tags, ID3 chapter frames, plus a `<name>.chapters.txt` timestamp list.
  Chapters are detected from lines like "Chapter 1 …", "Section …", "Part …".

## Project layout
```
audiobook/extractor.py   PDF/TXT text extraction
audiobook/processor.py   cleaning, chunking, chapter detection
audiobook/engines.py     pyttsx3 + gTTS engines
audiobook/converter.py   pipeline, pydub merge, export, metadata
audiobook/cli.py         command line      gui.py  Tkinter GUI
app.py + templates/ + static/   the website
tests/test_pipeline.py   run: python -m unittest discover -s tests
```
Note: scanned (image-only) PDFs contain no text; they need OCR first.
