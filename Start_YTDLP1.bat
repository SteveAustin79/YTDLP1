@echo off
venv\Scripts\activate
venv\Scripts\python.exe -m pip install yt_dlp
venv\Scripts\python.exe ytdl_cli.py
pause
