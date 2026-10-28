"""Desktop GUI (Tkinter).  Run:  python gui.py"""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from audiobook import AudiobookConverter, ConversionError
from audiobook.engines import Pyttsx3Engine, TTSError, get_engine

LANGS = {"English": "en", "Hindi": "hi", "Marathi": "mr", "French": "fr",
         "Spanish": "es", "German": "de", "Tamil": "ta", "Bengali": "bn"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio Book Using Python")
        self.geometry("640x560")
        self.q = queue.Queue()
        self.stop = False
        self.voices = []

        self.src = tk.StringVar(); self.dst = tk.StringVar()
        self.title_v = tk.StringVar(); self.author = tk.StringVar(value="Unknown")
        self.engine = tk.StringVar(value="gtts")
        self.lang = tk.StringVar(value="English")
        self.rate = tk.IntVar(value=170)
        self.voice = tk.StringVar()

        f = ttk.Frame(self, padding=12); f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        def row(r, label, var, browse=None):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(f, textvariable=var).grid(row=r, column=1, sticky="ew", padx=6)
            if browse:
                ttk.Button(f, text="Browse", command=browse).grid(row=r, column=2)

        row(0, "Input (PDF/TXT)", self.src, self.pick_src)
        row(1, "Output (MP3/WAV)", self.dst, self.pick_dst)
        row(2, "Title", self.title_v)
        row(3, "Author", self.author)

        ttk.Label(f, text="Engine").grid(row=4, column=0, sticky="w", pady=3)
        eb = ttk.Frame(f); eb.grid(row=4, column=1, sticky="w", padx=6)
        ttk.Radiobutton(eb, text="gTTS (online, natural)", variable=self.engine,
                        value="gtts", command=self.toggle).pack(side="left")
        ttk.Radiobutton(eb, text="pyttsx3 (offline)", variable=self.engine,
                        value="pyttsx3", command=self.toggle).pack(side="left", padx=10)

        self.lang_lbl = ttk.Label(f, text="Language")
        self.lang_cb = ttk.Combobox(f, textvariable=self.lang, values=list(LANGS),
                                    state="readonly")
        self.rate_lbl = ttk.Label(f, text="Speed (wpm)")
        self.rate_sc = ttk.Scale(f, from_=100, to=260, variable=self.rate,
                                 command=lambda v: self.rate.set(int(float(v))))
        self.voice_lbl = ttk.Label(f, text="Voice")
        self.voice_cb = ttk.Combobox(f, textvariable=self.voice, state="readonly")
        self.toggle()

        bb = ttk.Frame(f); bb.grid(row=8, column=0, columnspan=3, pady=10)
        self.go = ttk.Button(bb, text="Convert to Audiobook", command=self.start)
        self.go.pack(side="left", padx=4)
        self.cancel_b = ttk.Button(bb, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_b.pack(side="left", padx=4)

        self.bar = ttk.Progressbar(f, mode="determinate")
        self.bar.grid(row=9, column=0, columnspan=3, sticky="ew")
        self.logbox = tk.Text(f, height=14, state="disabled")
        self.logbox.grid(row=10, column=0, columnspan=3, sticky="nsew", pady=8)
        f.rowconfigure(10, weight=1)
        self.after(100, self.poll)

    def toggle(self):
        for w in (self.lang_lbl, self.lang_cb, self.rate_lbl, self.rate_sc,
                  self.voice_lbl, self.voice_cb):
            w.grid_forget()
        if self.engine.get() == "gtts":
            self.lang_lbl.grid(row=5, column=0, sticky="w")
            self.lang_cb.grid(row=5, column=1, sticky="ew", padx=6)
        else:
            if not self.voices:
                try:
                    self.voices = Pyttsx3Engine.list_voices()
                    self.voice_cb["values"] = [n for _, n in self.voices]
                    if self.voices: self.voice.set(self.voices[0][1])
                except Exception:
                    pass
            self.rate_lbl.grid(row=5, column=0, sticky="w")
            self.rate_sc.grid(row=5, column=1, sticky="ew", padx=6)
            self.voice_lbl.grid(row=6, column=0, sticky="w")
            self.voice_cb.grid(row=6, column=1, sticky="ew", padx=6)

    def pick_src(self):
        p = filedialog.askopenfilename(filetypes=[("Documents", "*.pdf *.txt")])
        if p:
            self.src.set(p)
            if not self.dst.get():
                self.dst.set(p.rsplit(".", 1)[0] + ".mp3")

    def pick_dst(self):
        p = filedialog.asksaveasfilename(defaultextension=".mp3",
                                         filetypes=[("MP3", "*.mp3"), ("WAV", "*.wav")])
        if p: self.dst.set(p)

    def log(self, m):
        self.q.put(("log", m))

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.logbox.config(state="normal")
                    self.logbox.insert("end", val + "\n"); self.logbox.see("end")
                    self.logbox.config(state="disabled")
                elif kind == "prog":
                    self.bar["maximum"] = val[1]; self.bar["value"] = val[0]
                elif kind == "done":
                    self.go.config(state="normal"); self.cancel_b.config(state="disabled")
                    (messagebox.showinfo if val[0] else messagebox.showerror)(
                        "Audio Book", val[1])
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def cancel(self):
        self.stop = True

    def start(self):
        if not self.src.get() or not self.dst.get():
            messagebox.showwarning("Missing", "Choose input and output files."); return
        self.stop = False
        self.go.config(state="disabled"); self.cancel_b.config(state="normal")
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        try:
            vid = next((i for i, n in self.voices if n == self.voice.get()), None)
            eng = get_engine(self.engine.get(), lang=LANGS.get(self.lang.get(), "en"),
                             rate=self.rate.get(), voice_id=vid)
            conv = AudiobookConverter(eng, cache_dir=".audiobook_cache", log=self.log,
                                      progress=lambda d, t: self.q.put(("prog", (d, t))),
                                      cancel=lambda: self.stop)
            r = conv.convert(self.src.get(), self.dst.get(), self.title_v.get(),
                             self.author.get() or "Unknown")
            self.q.put(("done", (True, f"Saved:\n{r['output']}")))
        except (ConversionError, TTSError) as e:
            self.q.put(("done", (False, str(e))))
        except Exception as e:
            self.q.put(("done", (False, f"Unexpected error: {e}")))


if __name__ == "__main__":
    App().mainloop()
