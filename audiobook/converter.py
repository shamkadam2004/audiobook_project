"""Stages 4-5 - Audio processing (pydub) and export with metadata."""
import hashlib
import os
import shutil
import time
from typing import Callable, List, Optional

from .engines import BaseEngine, TTSError, get_engine
from .extractor import ExtractionError, extract_text
from .processor import chunk_text, clean_text, split_chapters


class ConversionError(Exception):
    pass


def _fmt_ts(ms: int) -> str:
    s = ms // 1000
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


class AudiobookConverter:
    def __init__(self, engine: BaseEngine, max_chars: int = 1500, retries: int = 3,
                 pause_ms: int = 350, cache_dir: Optional[str] = None,
                 log: Callable[[str], None] = print,
                 progress: Callable[[int, int], None] = lambda d, t: None,
                 cancel: Callable[[], bool] = lambda: False):
        self.engine, self.max_chars, self.retries = engine, max_chars, retries
        self.pause_ms = pause_ms
        self.cache_dir = cache_dir
        self.log, self.progress, self.cancel = log, progress, cancel

    # ---- helpers ---------------------------------------------------------
    def _synth_with_retry(self, text: str, path: str) -> None:
        last = None
        for attempt in range(1, self.retries + 1):
            try:
                self.engine.synthesize(text, path)
                return
            except Exception as e:
                last = e
                self.log(f"  TTS attempt {attempt}/{self.retries} failed: {e}")
                time.sleep(min(2 * attempt, 5))
        raise ConversionError(f"Speech synthesis failed after retries: {last}")

    def _cached_chunk(self, text: str, tmp: str, idx: int) -> str:
        key = hashlib.sha1(
            f"{self.engine.name}|{vars(self.engine).get('lang','')}|"
            f"{vars(self.engine).get('rate','')}|{text}".encode()).hexdigest()
        ext = self.engine.file_ext
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
            cached = os.path.join(self.cache_dir, key + ext)
            if os.path.exists(cached) and os.path.getsize(cached) > 0:
                return cached
        path = os.path.join(tmp, f"chunk_{idx:05d}{ext}")
        self._synth_with_retry(text, path)
        if self.cache_dir:
            shutil.copy(path, cached)
            return cached
        return path

    # ---- main entry ------------------------------------------------------
    def convert(self, input_path: str, output_path: str, title: str = "",
                author: str = "Unknown", page_range: Optional[tuple] = None) -> dict:
        try:
            from pydub import AudioSegment
        except ImportError as e:
            raise ConversionError(f"pydub unavailable ({e}). Run: pip install -r requirements.txt") from e
        if not shutil.which("ffmpeg"):
            raise ConversionError("FFmpeg not found. Install it and add to PATH "
                                  "(see README).")

        self.log("[1/5] Extracting text ...")
        try:
            raw = extract_text(input_path, page_range, self.log)
        except ExtractionError as e:
            raise ConversionError(str(e)) from e

        self.log("[2/5] Cleaning and chunking ...")
        chapters = []
        for ch_title, body in split_chapters(clean_text(raw)):
            chunks = chunk_text(body, self.max_chars)
            if chunks:
                chapters.append((ch_title, chunks))
        total = sum(len(c) for _, c in chapters)
        if not total:
            raise ConversionError("Nothing to read after cleaning the text.")
        self.log(f"      {len(chapters)} chapter(s), {total} chunk(s)")

        tmp = os.path.join(os.path.dirname(os.path.abspath(output_path)),
                           f".tmp_{os.getpid()}")
        os.makedirs(tmp, exist_ok=True)
        try:
            self.log("[3/5] Synthesizing speech ...")
            audio = AudioSegment.silent(duration=200)
            markers, done, idx = [], 0, 0
            pause = AudioSegment.silent(duration=self.pause_ms)
            for ch_title, chunks in chapters:
                markers.append((ch_title, len(audio)))
                for text in chunks:
                    if self.cancel():
                        raise ConversionError("Cancelled by user.")
                    idx += 1
                    path = self._cached_chunk(text, tmp, idx)
                    try:
                        audio += AudioSegment.from_file(path) + pause
                    except Exception as e:
                        raise ConversionError(f"Cannot decode audio chunk: {e}")
                    done += 1
                    self.progress(done, total)
                    self.log(f"  chunk {done}/{total} done")

            self.log("[4/5] Exporting ...")
            fmt = os.path.splitext(output_path)[1].lower().lstrip(".") or "mp3"
            if fmt not in ("mp3", "wav"):
                raise ConversionError("Output must end with .mp3 or .wav")
            title = title or os.path.splitext(os.path.basename(input_path))[0]
            tags = {"title": title, "artist": author, "album": title,
                    "genre": "Audiobook"}
            audio.export(output_path, format=fmt, tags=tags if fmt == "mp3" else None)

            self.log("[5/5] Writing metadata & chapter markers ...")
            self._write_chapters(output_path, fmt, markers, len(audio))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        self.log(f"Done -> {output_path}  ({_fmt_ts(len(audio))})")
        return {"output": output_path, "duration_ms": len(audio),
                "chapters": [(t, s) for t, s in markers], "chunks": total}

    @staticmethod
    def _write_chapters(path: str, fmt: str, markers: List[tuple], total_ms: int):
        side = os.path.splitext(path)[0] + ".chapters.txt"
        with open(side, "w", encoding="utf-8") as f:
            for t, s in markers:
                f.write(f"{_fmt_ts(s)} {t}\n")
        if fmt != "mp3":
            return
        try:  # embed ID3 chapter frames (players like VLC/Apple Books read them)
            from mutagen.id3 import CHAP, CTOC, TIT2, ID3, CTOCFlags
            tags = ID3(path)
            ids = []
            for i, (t, s) in enumerate(markers):
                end = markers[i + 1][1] if i + 1 < len(markers) else total_ms
                cid = f"chp{i}"
                ids.append(cid)
                tags.add(CHAP(element_id=cid, start_time=s, end_time=end,
                              sub_frames=[TIT2(encoding=3, text=t)]))
            tags.add(CTOC(element_id="toc",
                          flags=CTOCFlags.TOP_LEVEL | CTOCFlags.ORDERED,
                          child_element_ids=ids,
                          sub_frames=[TIT2(encoding=3, text="Chapters")]))
            tags.save(v2_version=3)
        except Exception as e:
            print(f"  (chapter tags skipped: {e})")
