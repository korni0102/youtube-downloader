def download_with_ytdlp(url: str, fmt: str, tmpdir: str) -> str:
    ydl_opts = {
        "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,

        # >>> EZ ÚJ: kevésbé gyanús kliens (android)
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            }
        },
    }

    if fmt == "mp3":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        base = ydl.prepare_filename(info)
        title = safe_name(info.get("title") or "download")
        final_path = os.path.join(tmpdir, f"{title}.{'mp3' if fmt=='mp3' else 'mp4'}")
        if not os.path.exists(final_path):
            ext = "mp3" if fmt == "mp3" else "mp4"
            candidates = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.lower().endswith("." + ext)]
            if candidates:
                final_path = max(candidates, key=os.path.getmtime)
            else:
                final_path = os.path.splitext(base)[0] + f".{ext}"
        return final_path
