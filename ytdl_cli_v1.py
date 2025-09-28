import yt_dlp
import os
import re
import json
import subprocess
import glob

# ---------------------------
# Load configuration
# ---------------------------
CONFIG_FILE = "config.json"

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {"base_path": os.path.expanduser("~/YouTubeDownloads")}

BASE_PATH = os.path.expanduser(config.get("base_path", "~/YouTubeDownloads"))

# ---------------------------
# Helpers
# ---------------------------
def clean_string_regex(text: str) -> str:
    new_text = text.replace(":", "")
    pattern = r"[^a-zA-Z0-9 ]"
    return re.sub(pattern, "", new_text)

def get_info(url):
    """Fetch info about a video or playlist/channel."""
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": "web"}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def list_resolutions(info):
    """Return sorted available video resolutions (include mp4 and webm)."""
    formats = info.get("formats", [])
    video_streams = [
        f for f in formats
        if f.get("vcodec") != "none" and f.get("height") and f.get("ext") in ["mp4", "webm"]
    ]
    resolutions = sorted({f["height"] for f in video_streams})
    return resolutions

# ---------------------------
# Download functions
# ---------------------------
def download_audio(url, output_path=BASE_PATH):
    def sanitize(info, _):
        #info["title"] = sanitize_title(info["title"])
        info["title"] = clean_string_regex(info["title"])
        info["channel"] = clean_string_regex(info.get("channel") or info.get("uploader") or "UnknownChannel")
        return info

    info = get_info(url)
    print("\nChannel Name/Folder: " + BASE_PATH + "/" + clean_string_regex(info['channel']) + "\n")

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": os.path.join(
            output_path,
            "%(channel)s",
            "%(upload_date>%Y-%m-%d)s-%(title)s-%(id)s.%(ext)s"
        ),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "sanitize_info": sanitize,
        "extractor_args": {"youtube": {"player_client": "web"}},
    }
    os.makedirs(output_path, exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def download_video(url, resolution=None, output_path=BASE_PATH):
    """Download video, merge high-res webm+opus into MP4 H.264 + AAC"""
    info = get_info(url)
    formats = info.get("formats", [])

    os.makedirs(output_path, exist_ok=True)

    def sanitize(info, _):
        info["title"] = clean_string_regex(info["title"])
        info["channel"] = clean_string_regex(info.get("channel") or info.get("uploader") or "UnknownChannel")
        return info

    print("\nChannel Name/Folder: " + BASE_PATH + "/" + clean_string_regex(info['channel']) + "\n")

    if resolution and resolution > 1080:
        # High-res workflow
        video_fmt = next((f for f in formats if f.get("height") == resolution and f.get("vcodec") != "none"), None)
        if not video_fmt:
            print("❌ Requested resolution not found, using best video")
            fmt_vid = "bestvideo+bestaudio/best"
            output_file = os.path.join(output_path, "%(title)s.%(ext)s")
            with yt_dlp.YoutubeDL({
                "format": fmt_vid,
                "outtmpl": output_file,
                "extractor_args": {"youtube": {"player_client": "web"}},
                "sanitize_info": sanitize
            }) as ydl:
                ydl.download([url])
            return

        # Temporary file paths (no extension; yt-dlp will add .webm/.opus)
        video_path_base = os.path.join(output_path, "temp_video.webm")
        audio_path_base = os.path.join(output_path, "temp_audio")

        upload_date = info.get('upload_date', 'unknown')
        if upload_date != 'unknown' and len(upload_date) == 8:
            # Convert from YYYYMMDD → YYYY-MM-DD
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

        final_file = os.path.join(
            output_path,
            clean_string_regex(info['channel']),
            f"{upload_date} - {resolution}p - {clean_string_regex(info['title'])} - {info['id']}.mp4"
        )
        os.makedirs(os.path.dirname(final_file), exist_ok=True)

        # Download video only
        with yt_dlp.YoutubeDL({
            "format": f"{video_fmt['format_id']}",
            "outtmpl": video_path_base,
            "extractor_args": {"youtube": {"player_client": "web"}},
            "sanitize_info": sanitize
        }) as ydl:
            ydl.download([url])

        # Download audio only as opus
        with yt_dlp.YoutubeDL({
            "format": "bestaudio",
            "outtmpl": audio_path_base,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "opus"}],
            "extractor_args": {"youtube": {"player_client": "web"}},
            "sanitize_info": sanitize
        }) as ydl:
            ydl.download([url])

        # Detect actual audio file generated by yt-dlp
        audio_files = glob.glob(audio_path_base + ".*")
        if not audio_files:
            raise FileNotFoundError("Audio file not found after download")
        audio_file = audio_files[0]

        # Merge and re-encode into MP4 H.264 + AAC
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_path_base,
            "-i", audio_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            final_file
        ], check=True)

        # Remove temp files
        try:
            os.remove(video_path_base)
            os.remove(audio_file)
        except FileNotFoundError:
            pass

        print(f"✅ Video downloaded and merged to {final_file}")

    else:
        # <=1080p workflow
        fmt_str = f"bestvideo[height={resolution}]+bestaudio/best" if resolution else "bestvideo+bestaudio/best"
        output_file = os.path.join(
            output_path,
            "%(channel)s",
            "%(upload_date>%Y-%m-%d)s - %(height)sp - %(title)s - %(id)s.%(ext)s"
        )

        with yt_dlp.YoutubeDL({
            "format": fmt_str,
            "merge_output_format": "mp4",
            "recode-video": "mp4",
            "sanitize_info": sanitize,
            "extractor_args": {"youtube": {"player_client": "web"}}
        }) as ydl:
            ydl.download([url])

# ---------------------------
# Main loop
# ---------------------------
def main():
    print("=== YouTube Downloader (High-res webm -> MP4 H.264/AAC) ===")
    print(f"Base download path: {BASE_PATH}")
    url = input("Enter YouTube URL, video ID, or channel URL (or 'q' to quit): ").strip()
    if url.lower() == "q":
        return False  # exit loop

    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={url}"

    choice = input("Download (a)udio or (v)ideo? [a/v]: ").strip().lower()
    if choice == "a":
        download_audio(url)
        print("✅ Audio downloaded successfully.")
    else:
        info = get_info(url)
        resolutions = list_resolutions(info)
        if not resolutions:
            print("No resolutions available.")
            return True

        print("Available resolutions:")
        for i, r in enumerate(resolutions, 1):
            print(f"{i}. {r}p")

        sel = input(f"Select resolution [1-{len(resolutions)}] or press Enter for best: ").strip()
        res = None
        if sel.isdigit() and 1 <= int(sel) <= len(resolutions):
            res = resolutions[int(sel)-1]

        download_video(url, resolution=res)
        print("✅ Video downloaded successfully.")

    print()
    return True

if __name__ == "__main__":
    while True:
        if not main():
            print("👋 Exiting YouTube Downloader. Goodbye!")
            break
