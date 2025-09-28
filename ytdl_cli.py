import yt_dlp
import os
import re
import json
import subprocess
import glob

# ---------------------------
# Configuration
# ---------------------------
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {"base_path": os.path.expanduser("~/YouTubeDownloads")}

BASE_PATH = os.path.expanduser(config.get("base_path", "~/YouTubeDownloads"))

# ---------------------------
# Cookies setup
# ---------------------------
USE_COOKIES = True
COOKIES_FILE = BASE_PATH + "/cookies.txt" if USE_COOKIES else None

if USE_COOKIES:
    if not os.path.exists(COOKIES_FILE):
        raise FileNotFoundError(f"❌ Cookies file not found: {COOKIES_FILE}")
    print(f"🍪 Using cookies from: {COOKIES_FILE}")

# ---------------------------
# Helpers
# ---------------------------
def clean_string_regex(text: str) -> str:
    text = text.replace(":", "")
    pattern = r"[^a-zA-Z0-9 ]"
    return re.sub(pattern, "", text)

def get_info(url):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": "web"}}
    }
    if USE_COOKIES:
        ydl_opts["cookies"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def list_resolutions(info):
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
    info = get_info(url)
    upload_date = info.get('upload_date', 'unknown')
    if upload_date != 'unknown' and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    channel_folder = clean_string_regex(info.get("channel") or info.get("uploader") or "UnknownChannel")
    final_file = os.path.join(
        output_path,
        channel_folder,
        f"{upload_date} - {clean_string_regex(info['title'])} - {info['id']}.mp3"
    )
    os.makedirs(os.path.dirname(final_file), exist_ok=True)

    if os.path.exists(final_file):
        print(f"⚠️ Audio already exists, skipping: {final_file}")
        return

    def sanitize(info, _):
        info["title"] = clean_string_regex(info["title"])
        info["channel"] = clean_string_regex(info.get("channel") or info.get("uploader") or "UnknownChannel")
        return info

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": final_file,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        "sanitize_info": sanitize,
        "extractor_args": {"youtube": {"player_client": "web"}},
    }
    if USE_COOKIES:
        ydl_opts["cookies"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print(f"✅ Audio downloaded to {final_file}")

def download_video(url, resolution=None, output_path=BASE_PATH):
    info = get_info(url)
    formats = info.get("formats", [])
    os.makedirs(output_path, exist_ok=True)

    def sanitize(info, _):
        info["title"] = clean_string_regex(info["title"])
        info["channel"] = clean_string_regex(info.get("channel") or info.get("uploader") or "UnknownChannel")
        return info

    upload_date = info.get('upload_date', 'unknown')
    if upload_date != 'unknown' and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    channel_folder = clean_string_regex(info.get("channel") or info.get("uploader") or "UnknownChannel")

    final_file = os.path.join(
        output_path,
        channel_folder,
        f"{upload_date} - {resolution if resolution else 'best'}p - {clean_string_regex(info['title'])} - {info['id']}.mp4"
    )
    os.makedirs(os.path.dirname(final_file), exist_ok=True)

    if os.path.exists(final_file):
        print(f"⚠️ Video already exists, skipping: {final_file}")
        return

    # High-res >1080p workflow: download webm + opus → merge → MP4 H.264 + AAC
    if resolution and resolution > 1080:
        video_fmt = next((f for f in formats if f.get("height") == resolution and f.get("vcodec") != "none"), None)
        if not video_fmt:
            print("❌ Requested resolution not found, using best available")
            resolution = None

    if resolution and resolution > 1080 and video_fmt:
        # Temporary paths
        video_temp = os.path.join(output_path, "temp_video.webm")
        audio_temp = os.path.join(output_path, "temp_audio")

        # Download video only
        ydl_opts_video = {
            "format": f"{video_fmt['format_id']}",
            "outtmpl": video_temp,
            "extractor_args": {"youtube": {"player_client": "web"}},
            "sanitize_info": sanitize
        }
        if USE_COOKIES:
            ydl_opts_video["cookies"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([url])

        # Download audio only as opus
        ydl_opts_audio = {
            "format": "bestaudio",
            "outtmpl": audio_temp,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "opus"}],
            "extractor_args": {"youtube": {"player_client": "web"}},
            "sanitize_info": sanitize
        }
        if USE_COOKIES:
            ydl_opts_audio["cookies"] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([url])

        # Merge video + audio into MP4 H.264 + AAC
        audio_files = glob.glob(audio_temp + ".*")
        if not audio_files:
            raise FileNotFoundError("Audio file not found after download")
        audio_file = audio_files[0]

        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_temp,
            "-i", audio_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            final_file
        ], check=True)

        # Cleanup
        os.remove(video_temp)
        os.remove(audio_file)
        print(f"✅ Video downloaded and merged to {final_file}")
        return

    # <=1080p workflow
    fmt_str = f"bestvideo[height={resolution}]+bestaudio/best" if resolution else "bestvideo+bestaudio/best"
    ydl_opts = {
        "format": fmt_str,
        "merge_output_format": "mp4",
        "recode-video": "mp4",
        "sanitize_info": sanitize,
        "extractor_args": {"youtube": {"player_client": "web"}}
    }
    if USE_COOKIES:
        ydl_opts["cookies"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print(f"✅ Video downloaded to {final_file}")

# ---------------------------
# Main loop
# ---------------------------
def main():
    print("=== YouTube Downloader ===")
    print(f"Base download path: {BASE_PATH}")
    url = input("Enter YouTube URL, video ID, or channel URL (or 'q' to quit): ").strip()
    if url.lower() == "q":
        return False
    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={url}"

    choice = input("Download (a)udio or (v)ideo? [a/v]: ").strip().lower()
    if choice == "a":
        download_audio(url)
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
    return True

if __name__ == "__main__":
    while True:
        if not main():
            print("👋 Exiting YouTube Downloader. Goodbye!")
            break
