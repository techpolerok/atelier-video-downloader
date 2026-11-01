"""Persistent configuration management backed by QSettings."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QSettings


class AppSettings:
    """Typed wrapper around QSettings for persistent user preferences."""

    def __init__(self) -> None:
        """Initialize the QSettings store."""
        self._store = QSettings("AtelierDesktop", "AtelierVideoArchiver")

    def sync(self) -> None:
        """Flush pending changes to disk."""
        self._store.sync()

    # --- Output Settings ---

    @property
    def download_dir(self) -> str:
        """Return the default download folder path."""
        default_path = str(Path.home() / "Downloads")
        val = self._store.value("output/download_dir", default_path, type=str)
        return val if val else default_path

    @download_dir.setter
    def download_dir(self, path: str) -> None:
        self._store.setValue("output/download_dir", path.strip())

    @property
    def filename_template(self) -> str:
        """Return the yt-dlp output filename template."""
        default_tpl = "%(title)s.%(ext)s"
        val = self._store.value("output/filename_template", default_tpl, type=str)
        return val.strip() if val and val.strip() else default_tpl

    @filename_template.setter
    def filename_template(self, template: str) -> None:
        self._store.setValue(
            "output/filename_template",
            template.strip() or "%(title)s.%(ext)s",
        )

    # --- Queue & Concurrency Settings ---

    @property
    def max_concurrent_downloads(self) -> int:
        """Return the maximum number of simultaneous downloads (1 to 5)."""
        val = self._store.value("queue/max_concurrent", 2, type=int)
        return max(1, min(5, int(val)))

    @max_concurrent_downloads.setter
    def max_concurrent_downloads(self, count: int) -> None:
        self._store.setValue("queue/max_concurrent", max(1, min(5, int(count))))

    # --- Format & Media Preferences ---

    @property
    def media_mode(self) -> str:
        """Return the selected mode ('video' or 'audio')."""
        val = self._store.value("format/media_mode", "video", type=str)
        return val if val in ("video", "audio") else "video"

    @media_mode.setter
    def media_mode(self, mode: str) -> None:
        self._store.setValue("format/media_mode", mode)

    @property
    def video_resolution(self) -> str:
        """Return the preferred video resolution label."""
        val = self._store.value("format/video_resolution", "1080p", type=str)
        valid = ("Best", "2160p", "1440p", "1080p", "720p", "480p", "360p")
        return val if val in valid else "1080p"

    @video_resolution.setter
    def video_resolution(self, resolution: str) -> None:
        self._store.setValue("format/video_resolution", resolution)

    @property
    def video_container(self) -> str:
        """Return the preferred video container ('mp4', 'mkv', 'webm')."""
        val = self._store.value("format/video_container", "mp4", type=str)
        return val if val in ("mp4", "mkv", "webm") else "mp4"

    @video_container.setter
    def video_container(self, container: str) -> None:
        self._store.setValue("format/video_container", container)

    @property
    def audio_format(self) -> str:
        """Return the preferred audio codec ('mp3', 'm4a', 'opus', 'flac', 'wav')."""
        val = self._store.value("format/audio_format", "mp3", type=str)
        return val if val in ("mp3", "m4a", "opus", "flac", "wav") else "mp3"

    @audio_format.setter
    def audio_format(self, fmt: str) -> None:
        self._store.setValue("format/audio_format", fmt)

    @property
    def audio_quality(self) -> str:
        """Return the preferred audio bitrate ('128', '192', '256', '320')."""
        val = self._store.value("format/audio_quality", "192", type=str)
        return val if val in ("128", "192", "256", "320") else "192"

    @audio_quality.setter
    def audio_quality(self, quality: str) -> None:
        self._store.setValue("format/audio_quality", quality)

    @property
    def embed_thumbnail(self) -> bool:
        """Whether to embed the video thumbnail into the output file."""
        return self._store.value("format/embed_thumbnail", False, type=bool)

    @embed_thumbnail.setter
    def embed_thumbnail(self, enabled: bool) -> None:
        self._store.setValue("format/embed_thumbnail", bool(enabled))

    @property
    def embed_metadata(self) -> bool:
        """Whether to embed metadata tags into the output file."""
        return self._store.value("format/embed_metadata", True, type=bool)

    @embed_metadata.setter
    def embed_metadata(self, enabled: bool) -> None:
        self._store.setValue("format/embed_metadata", bool(enabled))

    @property
    def download_subtitles(self) -> bool:
        """Whether to download subtitles."""
        return self._store.value("format/download_subtitles", False, type=bool)

    @download_subtitles.setter
    def download_subtitles(self, enabled: bool) -> None:
        self._store.setValue("format/download_subtitles", bool(enabled))

    @property
    def subtitle_language(self) -> str:
        """Return the subtitle language code (e.g. 'en', 'es', 'all')."""
        val = self._store.value("format/subtitle_language", "en", type=str)
        return val if val else "en"

    @subtitle_language.setter
    def subtitle_language(self, lang: str) -> None:
        self._store.setValue("format/subtitle_language", lang.strip() or "en")

    @property
    def embed_subtitles(self) -> bool:
        """Whether to embed downloaded subtitles into the container."""
        return self._store.value("format/embed_subtitles", False, type=bool)

    @embed_subtitles.setter
    def embed_subtitles(self, enabled: bool) -> None:
        self._store.setValue("format/embed_subtitles", bool(enabled))

    # --- Advanced Settings ---

    @property
    def cookies_browser(self) -> str:
        """Browser name for cookies extraction ('', 'firefox', 'chrome', 'chromium')."""
        val = self._store.value("advanced/cookies_browser", "", type=str)
        valid = ("", "firefox", "chrome", "chromium")
        return val if val in valid else ""

    @cookies_browser.setter
    def cookies_browser(self, browser: str) -> None:
        self._store.setValue("advanced/cookies_browser", browser.lower().strip())

    @property
    def proxy_url(self) -> str:
        """Optional HTTP/SOCKS proxy URL."""
        return self._store.value("advanced/proxy_url", "", type=str) or ""

    @proxy_url.setter
    def proxy_url(self, proxy: str) -> None:
        self._store.setValue("advanced/proxy_url", proxy.strip())

    @property
    def rate_limit_kib(self) -> int:
        """Optional download speed limit in KiB/s (0 = unlimited)."""
        val = self._store.value("advanced/rate_limit_kib", 0, type=int)
        return max(0, int(val))

    @rate_limit_kib.setter
    def rate_limit_kib(self, kib: int) -> None:
        self._store.setValue("advanced/rate_limit_kib", max(0, int(kib)))

    # --- Appearance Settings ---

    @property
    def theme_mode(self) -> str:
        """Theme mode preference ('system', 'light', 'dark')."""
        val = self._store.value("ui/theme_mode", "system", type=str)
        return val if val in ("system", "light", "dark") else "system"

    @theme_mode.setter
    def theme_mode(self, mode: str) -> None:
        if mode in ("system", "light", "dark"):
            self._store.setValue("ui/theme_mode", mode)