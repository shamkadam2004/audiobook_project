"""Stage 3 - Speech synthesis engines: pyttsx3 (offline) and gTTS (online)."""
import os
import time
from typing import List


class TTSError(Exception):
    pass


class BaseEngine:
    name = "base"
    file_ext = ".wav"

    def synthesize(self, text: str, out_path: str) -> None:
        raise NotImplementedError


class Pyttsx3Engine(BaseEngine):
    """Offline engine using system voices (SAPI5 / NSSpeech / eSpeak)."""
    name = "pyttsx3"
    file_ext = ".wav"

    def __init__(self, rate: int = 170, volume: float = 1.0, voice_id: str = None):
        try:
            import pyttsx3
        except ImportError as e:
            raise TTSError("Install pyttsx3:  pip install pyttsx3") from e
        self._pyttsx3 = pyttsx3
        self.rate, self.volume, self.voice_id = rate, volume, voice_id

    @staticmethod
    def list_voices() -> List[tuple]:
        import pyttsx3
        eng = pyttsx3.init()
        voices = [(v.id, v.name) for v in eng.getProperty("voices")]
        eng.stop()
        return voices

    def synthesize(self, text: str, out_path: str) -> None:
        # A fresh engine per chunk avoids the known pyttsx3 run-loop hang.
        eng = self._pyttsx3.init()
        eng.setProperty("rate", self.rate)
        eng.setProperty("volume", self.volume)
        if self.voice_id:
            eng.setProperty("voice", self.voice_id)
        eng.save_to_file(text, out_path)
        eng.runAndWait()
        eng.stop()
        # some drivers finish writing slightly after runAndWait returns
        for _ in range(20):
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return
            time.sleep(0.1)
        raise TTSError("pyttsx3 produced no audio (is a system voice installed?)")


class GTTSEngine(BaseEngine):
    """Online engine - natural voices, 30+ languages, needs internet."""
    name = "gtts"
    file_ext = ".mp3"

    def __init__(self, lang: str = "en", slow: bool = False, tld: str = "com"):
        try:
            from gtts import gTTS
        except ImportError as e:
            raise TTSError("Install gTTS:  pip install gTTS") from e
        self._gTTS = gTTS
        self.lang, self.slow, self.tld = lang, slow, tld

    def synthesize(self, text: str, out_path: str) -> None:
        try:
            self._gTTS(text=text, lang=self.lang, slow=self.slow,
                       tld=self.tld).save(out_path)
        except Exception as e:
            raise TTSError(f"gTTS failed (check internet / language): {e}") from e


def get_engine(name: str, **kw) -> BaseEngine:
    name = name.lower()
    if name == "pyttsx3":
        return Pyttsx3Engine(**{k: v for k, v in kw.items()
                                if k in ("rate", "volume", "voice_id")})
    if name == "gtts":
        return GTTSEngine(**{k: v for k, v in kw.items()
                             if k in ("lang", "slow", "tld")})
    raise TTSError(f"Unknown engine '{name}' (use pyttsx3 or gtts)")
