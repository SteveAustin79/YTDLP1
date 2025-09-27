import yt_dlp
import os

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


def download_audio(url, output_path="."):
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video(url, resolution=None, output_path="."):
    if resolution:
        fmt = f"bestvideo[ext=mp4][height={resolution}]+bestaudio[ext=m4a]/best[ext=mp4]"
    else:
        fmt = "bestvideo+bestaudio/best"

    ydl_opts = {
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def main():
    print("=== Simple YouTube Downloader (yt-dlp) ===")
    url = input("Enter YouTube URL, video ID, or channel URL: ").strip()
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
            return
        
        print("Available resolutions:")
        for i, r in enumerate(resolutions, 1):
            print(f"{i}. {r}p")

        sel = input(f"Select resolution [1-{len(resolutions)}] or press Enter for best: ").strip()
        res = None
        if sel.isdigit() and 1 <= int(sel) <= len(resolutions):
            res = resolutions[int(sel)-1]

        download_video(url, resolution=res)
        print("✅ Video downloaded successfully.")


if __name__ == "__main__":
    main()
