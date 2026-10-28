"""Stage 2 - Text cleaning and chunking (avoids buffer / time limits)."""
import re
from typing import List


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"-\n(\w)", r"\1", text)            # re-join hyphenated line breaks
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)       # single newline -> space
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[^\S\n]*https?://\S+", " link ", text)
    text = "".join(ch for ch in text if ch.isprintable() or ch == "\n")
    return text.strip()


def split_sentences(paragraph: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    return [p for p in parts if p]


def chunk_text(text: str, max_chars: int = 1500) -> List[str]:
    """Split on paragraph/sentence boundaries so no chunk exceeds max_chars."""
    chunks, current = [], ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        for sent in split_sentences(para):
            while len(sent) > max_chars:       # very long sentence: hard split on space
                cut = sent.rfind(" ", 0, max_chars)
                cut = cut if cut > 0 else max_chars
                if len(current) + cut + 1 > max_chars:
                    flush()
                current += sent[:cut] + " "
                flush()
                sent = sent[cut:].strip()
            if len(current) + len(sent) + 1 > max_chars:
                flush()
            current += sent + " "
        current += "\n"
    flush()
    return chunks


_CHAPTER = re.compile(r"^\s*(chapter|section|part)\s+[\w\d.-]+.*$", re.I | re.M)


def split_chapters(text: str) -> List[tuple]:
    """Return [(title, body)]. Falls back to one 'Full Text' chapter."""
    marks = list(_CHAPTER.finditer(text))
    if len(marks) < 2:
        return [("Full Text", text)]
    out = []
    if marks[0].start() > 0 and text[:marks[0].start()].strip():
        out.append(("Introduction", text[:marks[0].start()]))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(0).strip(), text[m.end():end]))
    return out
