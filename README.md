YT-DLP command line v1

## Installation (Linux)
1. Clone repository:
```diff
git clone  https://github.com/SteveAustin79/YTDLP1.git
```
2. Change directory
```diff
cd YTDLP1.gui
```
3. Install python environment
```diff
python3 -m venv venv
venv/scripts/activate
```
4. Install dependencies
```diff
sudo apt-get install python3-tk (Windows: pip install tk)
```
```diff
sudo venv/bin/python3 -m pip install yt-dlp ffmpeg-python
```
5. Create and modify config.json
```diff
cp config.example.json config.json
nano config.json
```
6. Add channel URLs to channels.txt (optional)
```diff
nano channels.txt
```
7. Run the application
```diff
venv/bin/python3 main.py
```
