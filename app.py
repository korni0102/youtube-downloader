import os
import re
import tempfile
import shutil
from flask import (
    Flask, request, send_file, render_template, render_template_string, flash,
    redirect, url_for, after_this_request
)
import yt_dlp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# --- Beállítások ---
COOKIE_SECRET_PATH = "/etc/secrets/cookies.txt"            # Render Secret Files (ha működik)
COOKIE_UPLOAD_PATH = os.path.join(os.getcwd(), "data", "cookies.txt")  # ide mentjük az admin oldalon feltöltött sütit
os.makedirs(os.path.dirname(COOKIE_UPLOAD_PATH), exist_ok=True)

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "changeme")    # Állítsd be Render → Environment-ben

# --- Segéd ---
def safe_name(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "download"

def pick_cookiefile(tmpdir: str) -> str | None:
    """
    Visszaadja a használható cookies.txt útvonalát:
    1) YTDLP_COOKIES env → ideiglenes fájlba írjuk
    2) Secret Files (/etc/secrets/cookies.txt), ha létezik
    3) Feltöltött fájl (data/cookies.txt), ha létezik
    """
    # 1) Env változó
    env_cookie = os.environ.get("YTDLP_COOKIES")
    if env_cookie:
        p = os.path.join(tmpdir, "cookies_env.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(env_cookie)
        return p

    # 2) Secret Files
    if os.path.exists(COOKIE_SECRET_PATH):
        cf = COOKIE_SECRET_PATH
    else:
        cf = None

    # 3) Feltöltött fájl (felülírhatja a Secret Files-t, ha az nem jó)
    if os.path.exists(COOKIE_UPLOAD_PATH):
        cf = COOKIE_UPLOAD_PATH

    return cf

def build_ytdlp_opts(tmpdir: str, fmt: str, player_client: str | None = None) -> dict:
    """
    Összerakja az yt-dlp opciókat. A player_client lehet: 'android', 'ios', 'web'.
    """
    opts = {
        "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "force_ipv4": True,              # néha ez segít a hívásoknál
        "retries": 3,
        "fragment_retries": 3,
        "retry_sleep": "1,2,3",
    }

    # kevésbé gyanús kliens – opciósan állítjuk
    if player_client:
        opts.setdefault("extractor_args", {})
        opts["extractor_args"].setdefault("youtube", {})
        opts["extractor_args"]["youtube"]["player_client"] = [player_client]

    # cookies forrás
    cookiefile = pick_cookiefile(tmpdir)
    if cookiefile:
        opts["cookiefile"] = cookiefile

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
    Több klienssel (android → ios → web) próbál letölteni.
    """
    clients_to_try = ["android", "ios", "web"]

    last_err = None
    for client in clients_to_try:
        try:
            opts = build_ytdlp_opts(tmpdir, fmt, player_client=client)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                base = ydl.prepare_filename(info)
                title = safe_name(info.get("title") or "download")
                ext = "mp3" if fmt == "mp3" else "mp4"
                target = os.path.join(tmpdir, f"{title}.{ext}")
                if not os.path.exists(target):
                    candidates = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.lower().endswith("." + ext)]
                    target = max(candidates, key=os.path.getmtime) if candidates else os.path.splitext(base)[0] + f".{ext}"
                print(f"[yt-dlp] success with client='{client}'", flush=True)
                return target
        except Exception as e:
            last_err = e
            print(f"[yt-dlp] failed with client='{client}': {e}", flush=True)
            continue

    # ha mindhárom kliens elbukott, dobjuk a hibát
    raise last_err if last_err else RuntimeError("yt-dlp: unknown error")

# --- Publikus oldalak ---
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

# --- Admin (cookies feltöltés / törlés) ---
ADMIN_HTML = """
<!doctype html><meta charset="utf-8">
<title>Admin – cookies</title>
<style>
body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:0;background:#0f172a;color:#e5e7eb}
main{max-width:780px;margin:40px auto;padding:0 16px}
.card{background:#111827;border:1px solid #1f2937;border-radius:14px;padding:18px}
h1{margin:0 0 12px}
label{display:block;margin:12px 0 6px;color:#94a3b8}
input[type=password],input[type=file]{width:100%;padding:10px;border-radius:10px;border:1px solid #1f2937;background:#0b1220;color:#e5e7eb}
.btn{margin-top:12px;padding:10px 14px;background:#22c55e;border:0;color:#0b1220;border-radius:10px;font-weight:700;cursor:pointer}
.warn{background:#7f1d1d;border:1px solid #b91c1c;padding:10px;border-radius:10px;margin:10px 0}
.meta{color:#94a3b8}
a{color:#93c5fd}
</style>
<main>
  <div class="card">
    <h1>Admin – cookies kezelő</h1>
    {% if not ok %}
      <p class="warn">Adj meg érvényes admin tokent!</p>
      <form method="get">
        <label>Admin token</label>
        <input type="password" name="token" required>
        <button class="btn">Belépés</button>
      </form>
      <p class="meta">Állítsd be Render → Environment: <code>ADMIN_TOKEN</code></p>
    {% else %}
      <p class="meta">Cookie állapot: <strong>{{ 'MEGVAN' if has_cookie else 'NINCS' }}</strong></p>
      <form method="post" action="/upload-cookies" enctype="multipart/form-data">
        <input type="hidden" name="token" value="{{ token }}">
        <label>cookies.txt (Netscape formátum)</label>
        <input type="file" name="file" accept=".txt" required>
        <button class="btn">Feltöltés</button>
      </form>
      <form method="post" action="/delete-cookies" style="margin-top:8px">
        <input type="hidden" name="token" value="{{ token }}">
        <button class="btn" style="background:#f59e0b">Törlés</button>
      </form>
      <p style="margin-top:10px"><a href="/">← Vissza a főoldalra</a></p>
    {% endif %}
  </div>
</main>
"""

def token_ok(req) -> bool:
    supplied = req.args.get("token") or req.form.get("token")
    return bool(ADMIN_TOKEN) and supplied == ADMIN_TOKEN

@app.route("/admin", methods=["GET"])
def admin():
    ok = token_ok(request)
    return render_template_string(
        ADMIN_HTML,
        ok=ok,
        has_cookie=os.path.exists(COOKIE_UPLOAD_PATH) or os.path.exists(COOKIE_SECRET_PATH),
        token=request.args.get("token", "") if ok else ""
    )

@app.route("/upload-cookies", methods=["POST"])
def upload_cookies():
    if not token_ok(request):
        return redirect(url_for("admin"))

    f = request.files.get("file")
    if not f:
        flash("Nem kaptam fájlt.")
        return redirect(url_for("admin", token=request.form.get("token")))

    data = f.read().decode("utf-8", errors="ignore")
    if "# Netscape HTTP Cookie File" not in data:
        flash("Nem Netscape formátumú cookies.txt.")
        return redirect(url_for("admin", token=request.form.get("token")))

    with open(COOKIE_UPLOAD_PATH, "w", encoding="utf-8") as out:
        out.write(data)

    flash("Cookies feltöltve.")
    return redirect(url_for("admin", token=request.form.get("token")))

@app.route("/delete-cookies", methods=["POST"])
def delete_cookies():
    if not token_ok(request):
        return redirect(url_for("admin"))
    try:
        if os.path.exists(COOKIE_UPLOAD_PATH):
            os.remove(COOKIE_UPLOAD_PATH)
        flash("Cookies törölve.")
    except Exception as e:
        flash(f"Nem sikerült törölni: {e}")
    return redirect(url_for("admin", token=request.form.get("token")))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
