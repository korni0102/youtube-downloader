import os
import re
import tempfile
from flask import Flask, request, send_file, render_template, flash, redirect, url_for
from pytube import YouTube
from moviepy.editor import AudioFileClip

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")  # flash üzenetekhez

# Fájlnév "megtisztítása"
def safe_name(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "download"

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

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

    # Munkamappa (ideiglenes)
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            if fmt == "mp3":
                # csak audio stream letöltése
                audio_stream = yt.streams.filter(only_audio=True).first()
                if not audio_stream:
                    flash("Nem találtam audio streamet ehhez a videóhoz.")
                    return redirect(url_for("index"))

                audio_path = audio_stream.download(output_path=tmpdir, filename="audio.webm")
                mp3_path = os.path.join(tmpdir, f"{title}.mp3")

                # Konvertálás MP3-ra (ffmpeg szükséges → apt.txt)
                clip = AudioFileClip(audio_path)
                clip.write_audiofile(mp3_path, verbose=False, logger=None)
                clip.close()

                return send_file(mp3_path, as_attachment=True, download_name=f"{title}.mp3")
            else:
                # MP4 videó letöltése legjobb elérhető felbontásban
                video_stream = yt.streams.get_highest_resolution()
                if not video_stream:
                    flash("Nem találtam videó streamet ehhez a videóhoz.")
                    return redirect(url_for("index"))

                mp4_path = video_stream.download(output_path=tmpdir, filename=f"{title}.mp4")
                return send_file(mp4_path, as_attachment=True, download_name=f"{title}.mp4")
        except Exception as e:
            flash(f"Hiba történt a letöltés/konvertálás közben: {e}")
            return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
