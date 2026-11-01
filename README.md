# Atelier Video Archiver (`yt-downloader`)

A native Linux graphical application for archiving YouTube videos, playlists, and channels using **Python 3.10+**, **PySide6 (Qt6)**, and **yt-dlp** (used directly as a Python library).

---

## Project Structure

```text
.
├── main.py
├── app/
│   ├── core/
│   │   ├── downloader.py      # yt-dlp library wrapper, error translator, QRunnable workers
│   │   ├── queue_manager.py   # Multi-threaded download queue & concurrency controller
│   │   └── settings.py        # Persistent QSettings wrapper
│   └── ui/
│       ├── main_window.py     # Main window, menus, toolbar, tray icon, and preview panel
│       ├── queue_table.py     # Queue table with progress bars & per-item action buttons
│       ├── settings_dialog.py # Cookies, proxy, rate-limit, and in-app yt-dlp updater
│       └── theme.py           # Centralized Light/Dark QSS stylesheet & QPainter icons
├── requirements.txt
├── yt-downloader.desktop
└── README.md
```

---

## Prerequisites (FFmpeg)

`ffmpeg` is required on your system `PATH` for merging high-resolution video streams (`1080p`–`2160p`) and converting audio formats (`mp3`, `m4a`, `opus`, `flac`, `wav`).

- **Debian / Ubuntu / Linux Mint:**
  ```bash
  sudo apt update && sudo apt install ffmpeg
  ```
- **Fedora / RHEL:**
  ```bash
  sudo dnf install ffmpeg
  ```
- **Arch Linux / Manjaro:**
  ```bash
  sudo pacman -S ffmpeg
  ```

---

## (a) Running from a Virtual Environment (`venv`)

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

---

## (b) Building a Standalone Binary with PyInstaller

1. **Install PyInstaller inside your virtual environment:**
   ```bash
   source .venv/bin/activate
   pip install pyinstaller
   ```

2. **Build a single-file Linux executable (`dist/yt-downloader`):**
   ```bash
   pyinstaller \
     --noconfirm \
     --clean \
     --windowed \
     --onefile \
     --name yt-downloader \
     --collect-all yt_dlp \
     main.py
   ```

3. **Run or install the binary:**
   ```bash
   ./dist/yt-downloader
   ```
   To integrate with your Linux desktop application menu:
   ```bash
   sudo cp dist/yt-downloader /usr/local/bin/yt-downloader
   cp yt-downloader.desktop ~/.local/share/applications/
   update-desktop-database ~/.local/share/applications/
   ```

---

## (c) Packaging as an AppImage (Optional)

1. **Build an onedir bundle using PyInstaller:**
   ```bash
   pyinstaller \
     --noconfirm \
     --clean \
     --windowed \
     --onedir \
     --name yt-downloader \
     --collect-all yt_dlp \
     main.py
   ```

2. **Prepare the `AppDir` directory layout:**
   ```bash
   mkdir -p AppDir/usr/bin AppDir/usr/share/applications
   cp -r dist/yt-downloader/* AppDir/usr/bin/
   cp yt-downloader.desktop AppDir/yt-downloader.desktop
   cp yt-downloader.desktop AppDir/usr/share/applications/

   # Create a simple SVG icon for AppImage metadata
   cat << 'EOF' > AppDir/video-x-generic.svg
   <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
     <rect x="4" y="4" width="56" height="56" rx="14" fill="#7A202E"/>
     <path d="M32 16v22M23 30l9 9 9-9M20 46h24" stroke="#FAF8F5" stroke-width="4" stroke-linecap="round" fill="none"/>
   </svg>
   EOF

   cat << 'EOF' > AppDir/AppRun
   #!/bin/sh
   HERE="$(dirname "$(readlink -f "${0}")")"
   exec "${HERE}/usr/bin/yt-downloader" "$@"
   EOF
   chmod +x AppDir/AppRun
   ```

3. **Download `appimagetool` and generate the `.AppImage`:**
   ```bash
   wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
   chmod +x appimagetool-x86_64.AppImage
   ARCH=x86_64 ./appimagetool-x86_64.AppImage AppDir Atelier_Video_Archiver-x86_64.AppImage
   ```

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl+V` | Paste URL from clipboard |
| `Enter` / `Return` | Fetch metadata for the URL in the input box |
| `Ctrl+Q` | Quit the application gracefully |