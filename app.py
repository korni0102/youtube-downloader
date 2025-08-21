import os
import re
import tempfile
import shutil
from flask import (
    Flask, request, send_file, render_template, flash,
    redirect, url_for, after_this_request
)
import yt_dlp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

def safe_name(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "download"

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/healthz")
def healthz():
    return "ok", 200

def download_with_ytdlp(url: str, fmt: str, tmpdir: str) -> str:
    """
    Letölt egy fájlt yt-dlp-vel a tmpdir-be és visszaadja a kész fájl abszolút elérési útját.
    fmt: 'mp3' vagy 'mp4'
    """
    # Alap opciók
    ydl_opts = {
        "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
    }

    if fmt == "mp3":
        # Hang kiszedése és MP3-ra alakítás ffmpeg-gel
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        # Jó minőségű MP4 (ha kell, össze is fűzi a videót + hangot)
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # A végső fájlnév (postprocess után) kiderítése:
        base = ydl.prepare_filename(info)  # ez még az eredeti kiterjesztés lehet
        title = safe_name(info.get("title") or "download")

        if fmt == "mp3":
            final_path = os.path.join(tmpdir, f"{title}.mp3")
        else:
            # ha merge_output_format=mp4, a végeredmény .mp4 lesz
            final_path = os.path.join(tmpdir, f"{title}.mp4")

        # Ha a fenti névvel nem létezik (néha nem “title”-lel nevez), keressük meg a legfrissebb fájlt a tmpdir-ben
        if not os.path.exists(final_path):
            # próbáljunk kiterjesztés szerint keresni
            ext = "mp3" if fmt == "mp3" else "mp4"
            candidates = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.lower().endswith("." + ext)]
            if candidates:
                # a legutóbb módosított
                final_path = max(candidates, key=os.path.getmtime)
            else:
                # utolsó mentsvár: a prepare_filename alapján
                if fmt == "mp3":
                    final_path = os.path.splitext(base)[0] + ".mp3"
                else:
                    final_path = os.path.splitext(base)[0] + ".mp4"

        return final_path

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url", "").strip()
    fmt = request.form.get("format", "mp4")
    if not url:
        flash("Adj meg egy YouTube URL-t!")
        return redirect(url_for("index"))
    if fmt not in ("mp3", "mp4"):
        fmt = "mp4"

    tmpdir = tempfile.mkdtemp(prefix="yt-")

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
        return response

    try:
        final_path = download_with_ytdlp(url, fmt, tmpdir)
        if not os.path.exists(final_path):
            flash("Nem sikerült a letöltés/konvertálás.")
            return redirect(url_for("index"))

        filename = os.path.basename(final_path)
        return send_file(final_path, as_attachment=True, download_name=filename)

    except yt_dlp.utils.YoutubeDLError as e:
        print(f"[YT-DLP ERROR] {e}", flush=True)
        flash("YouTube letöltési hiba (lehet, hogy a videó korlátozott vagy nem támogatott).")
        return redirect(url_for("index"))
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        flash(f"Hiba történt: {e}")
        return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
