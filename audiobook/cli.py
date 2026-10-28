"""Command-line interface:  python -m audiobook book.pdf -o book.mp3"""
import argparse
import sys

from .converter import AudiobookConverter, ConversionError
from .engines import Pyttsx3Engine, TTSError, get_engine


def main(argv=None):
    p = argparse.ArgumentParser(prog="audiobook",
                                description="Convert PDF/TXT into an audiobook.")
    p.add_argument("input", nargs="?", help=".pdf or .txt file")
    p.add_argument("-o", "--output", help="output .mp3 or .wav (default: input name .mp3)")
    p.add_argument("-e", "--engine", default="gtts", choices=["gtts", "pyttsx3"],
                   help="gtts = online/natural, pyttsx3 = offline")
    p.add_argument("-l", "--lang", default="en", help="gTTS language code (en, hi, mr, fr ...)")
    p.add_argument("--rate", type=int, default=170, help="pyttsx3 speech rate")
    p.add_argument("--voice", help="pyttsx3 voice id (see --list-voices)")
    p.add_argument("--slow", action="store_true", help="gTTS slow speech")
    p.add_argument("--title"); p.add_argument("--author", default="Unknown")
    p.add_argument("--pages", help="PDF page range e.g. 1-10")
    p.add_argument("--chunk", type=int, default=1500, help="max characters per chunk")
    p.add_argument("--cache", default=".audiobook_cache", help="chunk cache folder ('' to disable)")
    p.add_argument("--list-voices", action="store_true")
    a = p.parse_args(argv)

    if a.list_voices:
        try:
            for vid, name in Pyttsx3Engine.list_voices():
                print(f"{name}\n    {vid}")
        except Exception as e:
            print(f"Cannot list voices: {e}"); return 1
        return 0
    if not a.input:
        p.error("input file is required")

    out = a.output or a.input.rsplit(".", 1)[0] + ".mp3"
    pages = None
    if a.pages:
        try:
            x, _, y = a.pages.partition("-")
            pages = (int(x), int(y or x))
        except ValueError:
            p.error("--pages must look like 1-10")
    try:
        eng = get_engine(a.engine, lang=a.lang, slow=a.slow, rate=a.rate, voice_id=a.voice)
        AudiobookConverter(eng, max_chars=a.chunk, cache_dir=a.cache or None).convert(
            a.input, out, a.title or "", a.author, pages)
    except (ConversionError, TTSError) as e:
        print(f"ERROR: {e}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
