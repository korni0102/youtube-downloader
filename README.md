# YT → MP3/MP4 Downloader (Flask + yt-dlp + ffmpeg)

Egyszerű webalkalmazás, amellyel YouTube-videók **saját vagy engedélyezett** tartalma letölthető MP4/MP3 formátumban.
A projekt célja a **full-stack gondolkodás** bemutatása: backend logika, frontend űrlap, deploy felhőbe.

**Live demo:** https://YOUR-RENDER-URL

## Tech stack
- Backend: **Python Flask**
- Letöltés/konverzió: **yt-dlp**, **ffmpeg**
- UI: HTML + CSS (saját stílus)
- Deploy: **Render**
- (Opció) Auth bypass: **cookies.txt** Secret (Render Secret Files)

## Fő képességek, amiket demonstrál
- Flask routing, űrlapkezelés, fájlküldés
- Külső bináris eszközök integrálása (ffmpeg)
- Ideiglenes állományok kezelése és takarítása
- Cloud deploy, build/run parancsok beállítása
- Hibakezelés és logolás

## Használat
1. Illeszd be a YouTube URL-t, válassz formátumot (MP3/MP4), majd **Letöltés**.
2. A letöltött fájl a böngészőben automatikusan megjelenik.

> **Megjegyzés:** a YouTube gyakran kér botellenőrzést. A stabil működéshez Renderen **Secret Files** alatt töltsd fel a `cookies.txt`-t (Netscape formátum). A kód automatikusan használja.

## Fejlesztés lokálisan
```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_APP=app.py
python app.py
