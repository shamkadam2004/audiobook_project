"""Run:  python check_internet.py   - tests every online service the website uses."""
import app

for lang in ("hi", "mr"):
    for name, fn, _ in app.PROVIDERS:
        try:
            print(f"[OK]   translate {lang} via {name}: {fn('Good morning', lang)}")
        except Exception as e:
            print(f"[FAIL] translate {lang} via {name}: {type(e).__name__}: {str(e)[:150]}")
for lang in ("en", "hi", "mr"):
    try:
        print(f"[OK]   voice {lang}: {len(app.synthesize_mp3('Hello', lang))} bytes")
    except Exception as e:
        print(f"[FAIL] voice {lang}: {type(e).__name__}: {str(e)[:150]}")
