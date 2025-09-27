import yt_dlp
import os
import re
import json


# ---------------------------
# Load configuration
# ---------------------------
CONFIG_FILE = "config.json"

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    # fallback default if no config.json
    config = {"base_path": os.path.expanduser("~/YouTubeDownloads")}

BASE_PATH = os.path.expanduser(config.get("base_path", "~/YouTubeDownloads"))


# ---------------------------
# Helpers
# ---------------------------
def sanitize_title(title: str) -> str:
    """Remove special characters that are problematic for filenames."""
    return re.sub(r'[<>:"/\\|?*\']', '', title)


def get_info(url):
    """Fetch info about a video or playlist/channel."""
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def list_resolutions(info):
    """Return sorted available MP4 video resolutions."""
    formats = info.get("formats", [])
    video_streams = [
        f for f in formats
        if f.get("vcodec") != "none" and f.get("ext") == "mp4" and f.get("height")
    ]
    resolutions = sorted({f["height"] for f in video_streams})
    return resolutions


# ---------------------------
# Download functions
# ---------------------------
def download_audio(url, output_path=BASE_PATH):
    def sanitize(info, _):
        info["title"] = sanitize_title(info["title"])
        info["channel"] = sanitize_title(info.get("channel") or info.get("uploader") or "UnknownChannel")
        return info

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": os.path.join(
            output_path,
            "%(channel)s",
            "%(upload_date>%Y-%m-%d)s - AUDIO - %(title)s - %(id)s.%(ext)s"
        ),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }],
        "sanitize_info": sanitize
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video(url, resolution=None, output_path=BASE_PATH):
    """
    Downloads video and always re-encodes to MPEG-4 AVC (H.264) MP4
    for maximum VLC compatibility.
    """
    if resolution:
        fmt = f"bestvideo[height={resolution}]+bestaudio/best"
    else:
        fmt = "bestvideo+bestaudio/best"

    def sanitize(info, _):
        info["title"] = sanitize_title(info["title"])
        info["channel"] = sanitize_title(info.get("channel") or info.get("uploader") or "UnknownChannel")
        return info

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(
            output_path,
            "%(channel)s",
            "%(upload_date>%Y-%m-%d)s - %(height)sp - %(title)s - %(id)s.%(ext)s"
        ),
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
            "preferedcodec": "h264"  # <--- force H.264 re-encode
        }],
        "sanitize_info": sanitize
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])




# ---------------------------
# Main loop
# ---------------------------
def main():
    print("=== Simple YouTube Downloader (yt-dlp) ===")
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
