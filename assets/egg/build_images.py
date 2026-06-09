#!/usr/bin/env python3
"""
build_images.py — normalizza le immagini per l'opera audiovisiva FEEDBACK.

Cosa fa:
  - prende TUTTE le immagini da una cartella sorgente (default: la cartella padre)
  - le ridimensiona a max 1920px sul lato lungo
  - le ricodifica in JPG uniforme (qualita' 86), appiattite su nero
  - le salva in ./img/imgNN.jpg numerate in ordine alfabetico della sorgente
  - i giganti (es. JPG da centinaia di MB) vengono decodificati in modo ridotto (draft) per non saturare la RAM

Quando serve:
  - SOLO per aggiungere/sostituire immagini. La cartella img/ gia' generata e' autosufficiente.

Uso:
  python3 build_images.py [CARTELLA_SORGENTE]
  (se ometti la sorgente usa "..", cioe' la cartella padre)

Dipendenze: Pillow  ->  pip install Pillow
"""
import os, sys
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # consenti immagini enormi

SRC = sys.argv[1] if len(sys.argv) > 1 else ".."
OUT = "img"
MAXD = 1920
QUALITY = 86
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".jfif", ".bmp", ".tif", ".tiff")

os.makedirs(OUT, exist_ok=True)
files = sorted(f for f in os.listdir(SRC)
               if f.lower().endswith(EXTS) and os.path.isfile(os.path.join(SRC, f)))

ok, fail = 0, []
for f in files:
    p = os.path.join(SRC, f)
    try:
        im = Image.open(p)
        try: im.draft("RGB", (MAXD, MAXD))   # decodifica ridotta (jpeg enormi)
        except Exception: pass
        im = im.convert("RGB")               # appiattisce alpha/animazioni (primo frame)
        w, h = im.size
        s = min(1.0, MAXD / max(w, h))
        if s < 1.0:
            im = im.resize((max(1, int(w*s)), max(1, int(h*s))), Image.LANCZOS)
        ok += 1
        im.save(os.path.join(OUT, f"img{ok:02d}.jpg"), "JPEG", quality=QUALITY, optimize=True)
    except Exception as e:
        fail.append((f, str(e)[:80]))

print(f"Generate {ok} immagini in {OUT}/  (img01.jpg .. img{ok:02d}.jpg)")
if fail:
    print("Fallite:", len(fail))
    for f, e in fail: print("  -", f, "->", e)
print("\n>>> RICORDA: aggiorna  const N_IMG = <numero>  in index.html (ora dovrebbe valere", ok, ")")
