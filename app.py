import os
import re
import tempfile
import subprocess
import shutil
from flask import (
    Flask, request, send_file, render_template, flash,
    redirect, url_for, after_this_request
)
from pytube import YouTube

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

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url", "").strip()
    fmt = request.form.get("format", "mp4")

    if not url:
        flash("Adj meg egy YouTube URL-t!")
        return redirect(url_for("index"))

    try:
        yt = YouTube(url)
    except Exception as e:
        flash(f"Érvénytelen vagy nem elérhető URL: {e}")
        return redirect(url_for("index"))

    title = safe_name(yt.title)

    # KÉZZEL létrehozott temp mappa, amit csak a válasz UTÁN törlünk
    tmpdir = tempfile.mkdtemp(prefix="yt-")

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
        return response

    try:
        if fmt == "mp3":
            audio_stream = yt.streams.filter(only_audio=True).first()
            if not audio_stream:
                flash("Nem találtam audio streamet.")
                return redirect(url_for("index"))

            # forrás letöltése (pl. .webm vagy .m4a)
            src_path = audio_stream.download(output_path=tmpdir, filename="audio_src")
            dst_path = os.path.join(tmpdir, f"{title}.mp3")

            # ffmpeg konvertálás 192 kbps MP3-ra
            cmd = ["ffmpeg", "-y", "-i", src_path, "-vn", "-acodec", "libmp3lame", "-b:a", "192k", dst_path]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

            # A fájl a válasz küldése közben is megmarad, mert a törlés csak utána fut
            return send_file(dst_path, as_attachment=True, download_name=f"{title}.mp3")

        else:
            video_stream = yt.streams.get_highest_resolution()
            if not video_stream:
                flash("Nem találtam videó streamet.")
                return redirect(url_for("index"))

            mp4_path = video_stream.download(output_path=tmpdir, filename=f"{title}.mp4")
            return send_file(mp4_path, as_attachment=True, download_name=f"{title}.mp4")

    except subprocess.CalledProcessError:
        flash("Hiba az ffmpeg konvertálás közben.")
        return redirect(url_for("index"))
    except Exception as e:
        # Hibák naplózása Render logba
        print(f"[ERROR] {e}", flush=True)
        flash(f"Hiba történt: {e}")
        return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
