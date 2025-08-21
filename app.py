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

COOKIE_SECRET_PATH = "/etc/secrets/cookies.txt"  # Render Secret Files

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

def build_ytdlp_opts(tmpdir: str, fmt: str) -> dict:
    """
    Összerakja az yt-dlp opciókat. Ha van secret cookies.txt, hozzáadja.
    """
    opts = {
        "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        # kevésbé gyanús kliens
        "extractor_args": { "youtube": { "player_client": ["android"] } },
    }

    # Secret cookies fájl (ha létezik a Renderen)
    if os.path.exists(COOKIE_SECRET_PATH):
        opts["cookiefile"] = COOKIE_SECRET_PATH

    if fmt == "mp3":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })
    return opts

def run_ytdlp(url: str, fmt: str, tmpdir: str) -> str:
    """
    Letölt/konvertál yt-dlp-vel a tmpdir-be, és visszaadja a kész fájl abszolút elérési útját.
    """
    opts = build_ytdlp_opts(tmpdir, fmt)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        base = ydl.prepare_filename(info)
        title = safe_name(info.get("title") or "download")
        ext = "mp3" if fmt == "mp3" else "mp4"
        target = os.path.join(tmpdir, f"{title}.{ext}")

        # Ha a fenti név nem létezik, keressük meg a legutóbb írt azonos kiterjesztésű fájlt
        if not os.path.exists(target):
            candidates = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.lower().endswith("." + ext)]
            if candidates:
                target = max(candidates, key=os.path.getmtime)
            else:
                target = os.path.splitext(base)[0] + f".{ext}"
        return target

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url", "").strip()
    fmt = request.form.get("format", "mp4")
    if not url:
        flash("Adj meg egy YouTube URL-t!")
        return redirect(url_for("index"))
    if fmt not in ("mp3", "mp4"):
        fmt = "mp4"

    # Saját temp mappa — a választ KÖVETŐEN töröljük
    tmpdir = tempfile.mkdtemp(prefix="yt-")

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
        return response

    try:
        final_path = run_ytdlp(url, fmt, tmpdir)
        if not os.path.exists(final_path):
            flash("Nem sikerült a letöltés/konvertálás (lehet, hogy a videó korlátozott).")
            return redirect(url_for("index"))

        filename = os.path.basename(final_path)
        return send_file(final_path, as_attachment=True, download_name=filename)

    except yt_dlp.utils.ExtractorError as e:
        print(f"[YT-DLP ExtractorError] {e}", flush=True)
        flash("YouTube letöltési hiba (bot ellenőrzés vagy korlátozott videó).")
        return redirect(url_for("index"))
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        flash(f"Hiba történt: {e}")
        return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
