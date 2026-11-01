"""yt-dlp library integration, data structures, error formatting, and worker threads."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot
import yt_dlp
from yt_dlp.utils import DownloadError


class DownloadStatus(str, Enum):
    """Lifecycle states for an item in the download queue."""

    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    PROCESSING = "Processing"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELED = "Canceled"


class _PausedSignalError(Exception):
    """Internal exception raised inside a progress hook to pause cleanly."""


class _CanceledSignalError(Exception):
    """Internal exception raised inside a progress hook to cancel cleanly."""


@dataclass
class PlaylistEntry:
    """Metadata for a single item inside a playlist or channel."""

    entry_id: str
    title: str
    url: str
    duration: int | None = None
    channel: str = ""
    index: int = 1


@dataclass
class MediaInfo:
    """Extracted metadata for a single video, playlist, or channel."""

    url: str
    title: str
    channel: str
    duration: int | None
    thumbnail_url: str
    is_playlist: bool = False
    entries: list[PlaylistEntry] = field(default_factory=list)


@dataclass
class DownloadOptions:
    """Configuration snapshot for a single download task."""

    media_mode: str = "video"  # "video" or "audio"
    video_resolution: str = "1080p"  # Best, 2160p, 1440p, 1080p, 720p, 480p, 360p
    video_container: str = "mp4"  # mp4, mkv, webm
    audio_format: str = "mp3"  # mp3, m4a, opus, flac, wav
    audio_quality: str = "192"  # 128, 192, 256, 320
    embed_thumbnail: bool = False
    embed_metadata: bool = True
    download_subtitles: bool = False
    subtitle_language: str = "en"
    embed_subtitles: bool = False
    download_dir: str = str(Path.home() / "Downloads")
    filename_template: str = "%(title)s.%(ext)s"
    cookies_browser: str = ""
    proxy_url: str = ""
    rate_limit_kib: int = 0


@dataclass
class QueueItem:
    """State model for an entry in the download queue."""

    item_id: str
    url: str
    title: str
    options: DownloadOptions
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    speed_str: str = "—"
    eta_str: str = "—"
    size_str: str = "—"
    output_dir: str = ""
    output_filepath: str = ""
    error_message: str = ""


ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove terminal ANSI color escape sequences from yt-dlp messages."""
    return ANSI_ESCAPE_RE.sub("", text or "").strip()


def format_duration(seconds: int | float | None) -> str:
    """Format duration in seconds into HH:MM:SS or MM:SS."""
    if seconds is None or seconds < 0:
        return "Live / Unknown"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_bytes(num_bytes: float | int | None) -> str:
    """Format byte count into a human-readable string (KiB, MiB, GiB)."""
    if num_bytes is None or num_bytes <= 0:
        return "—"
    value = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024.0 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024.0
    return f"{value:.1f} TiB"


def check_ffmpeg_installed() -> bool:
    """Verify whether the ffmpeg binary is available on the system PATH."""
    return shutil.which("ffmpeg") is not None


def get_ffmpeg_install_instructions() -> str:
    """Return distribution-specific terminal commands to install ffmpeg."""
    return (
        "FFmpeg was not detected on your system PATH. Merging high-resolution video "
        "streams and converting audio formats require FFmpeg.\n\n"
        "Install it using your Linux distribution's package manager:\n"
        "  • Debian / Ubuntu / Mint:   sudo apt update && sudo apt install ffmpeg\n"
        "  • Fedora / RHEL:            sudo dnf install ffmpeg\n"
        "  • Arch Linux / Manjaro:     sudo pacman -S ffmpeg"
    )


def get_yt_dlp_version() -> str:
    """Return the currently loaded yt-dlp library version string."""
    return getattr(yt_dlp.version, "__version__", "Unknown")


def humanize_yt_dlp_error(exc: Exception) -> str:
    """Translate raw yt-dlp exceptions into clear, human-readable explanations."""
    raw = strip_ansi(str(exc))
    lower = raw.lower()

    if "private video" in lower or "sign in if you've been granted access" in lower:
        return (
            "This video is private. Enable 'Cookies from Browser' in Settings "
            "if your account has permission to view it."
        )
    if "sign in to confirm your age" in lower or "age-restricted" in lower or "inappropriate for some users" in lower:
        return (
            "Age-restricted video. Please enable 'Cookies from Browser' (Firefox/Chrome) "
            "in Settings to authenticate."
        )
    if "not available in your country" in lower or "geo" in lower and "blocked" in lower:
        return (
            "Geo-blocked content: The uploader has restricted this video in your region. "
            "Consider configuring a Proxy in Settings."
        )
    if "unsupported url" in lower or "is not a valid url" in lower:
        return "Invalid or unsupported URL. Please paste a valid YouTube video, playlist, or channel link."
    if "video unavailable" in lower or "this video has been removed" in lower:
        return "This video is unavailable or has been removed by the creator."
    if "ffmpeg" in lower and ("not found" in lower or "not installed" in lower):
        return "FFmpeg is missing on your system. Please install ffmpeg (apt/dnf/pacman) to merge or convert media."
    if any(
        net_err in lower
        for net_err in (
            "name or service not known",
            "temporary failure in name resolution",
            "network is unreachable",
            "connection reset",
            "timed out",
            "unable to download webpage",
        )
    ):
        return "Network connection error. Please check your internet connection or proxy settings."
    if "cookies" in lower and ("could not find" in lower or "permission" in lower or "database" in lower):
        return "Could not read cookies from the selected browser. Check that the browser is installed and has a profile."

    # Clean prefix clutter from yt-dlp error strings
    cleaned = re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*[^:]+:\s*)?", "", raw)
    return cleaned if cleaned else "An unexpected error occurred during processing."


class _YtDlpLogger:
    """Custom logger bridge that forwards yt-dlp output to a Qt callback."""

    def __init__(self, callback: Any) -> None:
        self._callback = callback

    def debug(self, msg: str) -> None:
        clean = strip_ansi(msg)
        if clean and not clean.startswith("[debug]"):
            self._callback(f"[INFO] {clean}")

    def info(self, msg: str) -> None:
        clean = strip_ansi(msg)
        if clean:
            self._callback(f"[INFO] {clean}")

    def warning(self, msg: str) -> None:
        clean = strip_ansi(msg)
        if clean:
            self._callback(f"[WARN] {clean}")

    def error(self, msg: str) -> None:
        clean = strip_ansi(msg)
        if clean:
            self._callback(f"[ERROR] {clean}")


def build_ydl_options(
    options: DownloadOptions,
    logger: _YtDlpLogger,
    progress_hook: Any,
    postprocessor_hook: Any,
) -> dict[str, Any]:
    """Construct the yt-dlp configuration dictionary from DownloadOptions."""
    out_dir = Path(options.download_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(out_dir / options.filename_template)

    postprocessors: list[dict[str, Any]] = []

    if options.media_mode == "audio":
        format_selector = "bestaudio/best"
        audio_pp: dict[str, Any] = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": options.audio_format,
        }
        if options.audio_format not in ("flac", "wav"):
            audio_pp["preferredquality"] = options.audio_quality
        postprocessors.append(audio_pp)
    else:
        res = options.video_resolution
        if res == "Best":
            format_selector = "bestvideo+bestaudio/best"
        else:
            height = res.rstrip("p")
            format_selector = (
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]/best"
            )

    if options.embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

    if options.embed_thumbnail:
        # EmbedThumbnail is supported for mp3, mkv, mp4, m4a,ogg, opus, flac
        supported_thumb = (
            options.audio_format not in ("wav",)
            if options.media_mode == "audio"
            else options.video_container in ("mp4", "mkv")
        )
        if supported_thumb:
            postprocessors.append({"key": "EmbedThumbnail"})

    if options.download_subtitles and options.embed_subtitles and options.media_mode == "video":
        postprocessors.append({"key": "FFmpegEmbedSubtitle"})

    ydl_opts: dict[str, Any] = {
        "format": format_selector,
        "outtmpl": {"default": outtmpl},
        "continuedl": True,
        "noplaylist": True,
        "noprogress": False,
        "quiet": True,
        "no_warnings": False,
        "logger": logger,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "postprocessors": postprocessors,
        "writethumbnail": bool(options.embed_thumbnail),
    }

    if options.media_mode == "video":
        ydl_opts["merge_output_format"] = options.video_container

    if options.download_subtitles:
        langs = [
            lang.strip()
            for lang in options.subtitle_language.split(",")
            if lang.strip()
        ]
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        ydl_opts["subtitleslangs"] = langs or ["en"]

    if options.cookies_browser:
        ydl_opts["cookiesfrombrowser"] = (options.cookies_browser,)

    if options.proxy_url:
        ydl_opts["proxy"] = options.proxy_url

    if options.rate_limit_kib > 0:
        ydl_opts["ratelimit"] = int(options.rate_limit_kib) * 1024

    return ydl_opts


class InfoFetchSignals(QObject):
    """Qt signals emitted by InfoFetchWorker."""

    finished = Signal(object)  # MediaInfo
    error = Signal(str)
    log = Signal(str)


class InfoFetchWorker(QRunnable):
    """Background worker that extracts video or playlist metadata via yt-dlp."""

    def __init__(
        self,
        url: str,
        cookies_browser: str = "",
        proxy_url: str = "",
    ) -> None:
        super().__init__()
        self.url = url.strip()
        self.cookies_browser = cookies_browser.strip()
        self.proxy_url = proxy_url.strip()
        self.signals = InfoFetchSignals()

    @Slot()
    def run(self) -> None:
        """Perform metadata extraction without downloading media streams."""
        logger = _YtDlpLogger(self.signals.log.emit)
        ydl_opts: dict[str, Any] = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": False,
            "logger": logger,
            "socket_timeout": 20,
        }
        if self.cookies_browser:
            ydl_opts["cookiesfrombrowser"] = (self.cookies_browser,)
        if self.proxy_url:
            ydl_opts["proxy"] = self.proxy_url

        try:
            self.signals.log.emit(f"[INFO] Fetching metadata for: {self.url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if not info:
                    raise DownloadError("No metadata returned for this URL.")

                # Determine if the extracted entity is a playlist or channel
                is_playlist = info.get("_type") in ("playlist", "multi_video") or "entries" in info
                title = info.get("title") or info.get("id") or "Untitled Media"
                channel = (
                    info.get("uploader")
                    or info.get("channel")
                    or info.get("uploader_id")
                    or "YouTube Creator"
                )
                duration = info.get("duration")
                thumb = self._select_thumbnail(info)

                entries_list: list[PlaylistEntry] = []
                if is_playlist:
                    raw_entries = list(info.get("entries") or [])
                    # Flatten nested channel tabs if entries themselves are playlists
                    flattened: list[dict[str, Any]] = []
                    for item in raw_entries:
                        if not item:
                            continue
                        if item.get("_type") == "playlist" and item.get("entries"):
                            flattened.extend([e for e in item.get("entries") if e])
                        else:
                            flattened.append(item)

                    for idx, entry in enumerate(flattened, start=1):
                        e_id = str(entry.get("id") or idx)
                        e_title = entry.get("title") or f"Video #{idx}"
                        if e_title in ("[Private video]", "[Deleted video]"):
                            continue
                        e_url = (
                            entry.get("url")
                            or entry.get("webpage_url")
                            or f"https://www.youtube.com/watch?v={e_id}"
                        )
                        if not e_url.startswith("http"):
                            e_url = f"https://www.youtube.com/watch?v={e_id}"
                        e_dur = entry.get("duration")
                        e_chan = entry.get("uploader") or entry.get("channel") or channel
                        entries_list.append(
                            PlaylistEntry(
                                entry_id=e_id,
                                title=e_title,
                                url=e_url,
                                duration=int(e_dur) if isinstance(e_dur, (int, float)) else None,
                                channel=e_chan,
                                index=idx,
                            )
                        )
                    if not thumb and flattened:
                        thumb = self._select_thumbnail(flattened[0])

                media_info = MediaInfo(
                    url=info.get("webpage_url") or self.url,
                    title=title,
                    channel=channel,
                    duration=int(duration) if isinstance(duration, (int, float)) else None,
                    thumbnail_url=thumb,
                    is_playlist=is_playlist and len(entries_list) > 0,
                    entries=entries_list,
                )
                self.signals.log.emit(
                    f"[INFO] Metadata fetched: '{media_info.title}' "
                    f"({len(entries_list)} playlist items)" if media_info.is_playlist
                    else f"[INFO] Metadata fetched: '{media_info.title}'"
                )
                self.signals.finished.emit(media_info)
        except Exception as exc:
            friendly = humanize_yt_dlp_error(exc)
            self.signals.log.emit(f"[ERROR] Metadata fetch failed: {friendly}")
            self.signals.error.emit(friendly)

    @staticmethod
    def _select_thumbnail(info_dict: dict[str, Any]) -> str:
        """Pick a suitable HTTP thumbnail URL from a yt-dlp info dictionary."""
        direct = info_dict.get("thumbnail")
        if isinstance(direct, str) and direct.startswith("http"):
            return direct
        thumbs = info_dict.get("thumbnails")
        if isinstance(thumbs, list) and thumbs:
            for candidate in reversed(thumbs):
                url = candidate.get("url") if isinstance(candidate, dict) else None
                if isinstance(url, str) and url.startswith("http"):
                    return url
        vid_id = info_dict.get("id")
        if isinstance(vid_id, str) and len(vid_id) == 11:
            return f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
        return ""


class DownloadSignals(QObject):
    """Qt signals emitted by DownloadWorker during execution."""

    progress = Signal(str, float, str, str, str)  # item_id, pct, speed, eta, size
    status_changed = Signal(str, str, str)  # item_id, DownloadStatus.value, message/path
    log = Signal(str)


class DownloadWorker(QRunnable):
    """Worker runnable that downloads a single QueueItem using yt-dlp."""

    def __init__(self, item: QueueItem) -> None:
        super().__init__()
        self.item = item
        self.signals = DownloadSignals()
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()

    def request_pause(self) -> None:
        """Signal the running download to pause cleanly on the next chunk."""
        self._pause_event.set()

    def request_cancel(self) -> None:
        """Signal the running download to abort immediately."""
        self._cancel_event.set()

    def _check_interruption(self) -> None:
        """Raise internal signal exceptions if pause or cancel was requested."""
        if self._cancel_event.is_set():
            raise _CanceledSignalError()
        if self._pause_event.is_set():
            raise _PausedSignalError()

    def _progress_hook(self, d: dict[str, Any]) -> None:
        """Handle real-time progress callbacks from yt-dlp."""
        self._check_interruption()

        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total > 0:
                pct = min(99.9, max(0.0, (float(downloaded) / float(total)) * 100.0))
                size_str = format_bytes(total)
            else:
                pct = 0.0
                size_str = format_bytes(downloaded)

            speed = d.get("speed")
            speed_str = f"{format_bytes(speed)}/s" if speed else "—"

            eta = d.get("eta")
            eta_str = format_duration(eta) if isinstance(eta, (int, float)) else "—"

            self.signals.progress.emit(
                self.item.item_id,
                pct,
                speed_str,
                eta_str,
                size_str,
            )
        elif status == "finished":
            total = d.get("total_bytes") or d.get("downloaded_bytes") or 0
            filename = d.get("filename") or ""
            self.signals.progress.emit(
                self.item.item_id,
                100.0,
                "—",
                "00:00",
                format_bytes(total),
            )
            if filename:
                self.item.output_filepath = str(filename)

    def _postprocessor_hook(self, d: dict[str, Any]) -> None:
        """Handle post-processing transitions (FFmpeg merging, audio conversion)."""
        self._check_interruption()
        status = d.get("status")
        if status == "started":
            self.signals.status_changed.emit(
                self.item.item_id,
                DownloadStatus.PROCESSING.value,
                "",
            )
        elif status == "finished":
            info_dict = d.get("info_dict") or {}
            filepath = info_dict.get("filepath") or info_dict.get("_filename")
            if filepath:
                self.item.output_filepath = str(filepath)

    @Slot()
    def run(self) -> None:
        """Execute the yt-dlp download workflow on a background thread."""
        item_id = self.item.item_id
        logger = _YtDlpLogger(self.signals.log.emit)

        try:
            self._check_interruption()
            self.signals.status_changed.emit(
                item_id,
                DownloadStatus.DOWNLOADING.value,
                "",
            )
            self.signals.log.emit(f"[INFO] Starting download: '{self.item.title}'")

            ydl_opts = build_ydl_options(
                options=self.item.options,
                logger=logger,
                progress_hook=self._progress_hook,
                postprocessor_hook=self._postprocessor_hook,
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.item.url])

            self.signals.log.emit(f"[INFO] Completed download: '{self.item.title}'")
            self.signals.status_changed.emit(
                item_id,
                DownloadStatus.COMPLETED.value,
                self.item.output_filepath or self.item.options.download_dir,
            )

        except _PausedSignalError:
            self.signals.log.emit(f"[INFO] Paused download: '{self.item.title}'")
            self.signals.status_changed.emit(
                item_id,
                DownloadStatus.PAUSED.value,
                "",
            )
        except _CanceledSignalError:
            self.signals.log.emit(f"[INFO] Canceled download: '{self.item.title}'")
            self.signals.status_changed.emit(
                item_id,
                DownloadStatus.CANCELED.value,
                "",
            )
        except Exception as exc:
            # Check if pause/cancel triggered a wrapped yt-dlp exception
            if self._cancel_event.is_set():
                self.signals.status_changed.emit(
                    item_id,
                    DownloadStatus.CANCELED.value,
                    "",
                )
                return
            if self._pause_event.is_set():
                self.signals.status_changed.emit(
                    item_id,
                    DownloadStatus.PAUSED.value,
                    "",
                )
                return

            friendly_err = humanize_yt_dlp_error(exc)
            self.signals.log.emit(
                f"[ERROR] Failed '{self.item.title}': {friendly_err}"
            )
            self.signals.status_changed.emit(
                item_id,
                DownloadStatus.FAILED.value,
                friendly_err,
            )


class UpdateYtDlpSignals(QObject):
    """Qt signals emitted by UpdateYtDlpWorker."""

    finished = Signal(bool, str, str)  # success, message, new_version
    log = Signal(str)


class UpdateYtDlpWorker(QRunnable):
    """Worker runnable that upgrades yt-dlp inside the active Python environment."""

    def __init__(self) -> None:
        super().__init__()
        self.signals = UpdateYtDlpSignals()

    @Slot()
    def run(self) -> None:
        """Run `pip install -U yt-dlp` using the current interpreter."""
        cmd = [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"]
        self.signals.log.emit(f"[INFO] Running update: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            for line in output.splitlines():
                if line.strip():
                    self.signals.log.emit(f"[PIP] {line.strip()}")

            if proc.returncode == 0:
                # Query updated version from subprocess so we get the newly installed package version
                ver_proc = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import yt_dlp; print(yt_dlp.version.__version__)",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                new_ver = ver_proc.stdout.strip() or get_yt_dlp_version()
                self.signals.finished.emit(
                    True,
                    f"yt-dlp is up to date (version {new_ver}).",
                    new_ver,
                )
            else:
                err_summary = proc.stderr.strip() or "pip returned a non-zero exit code."
                self.signals.finished.emit(
                    False,
                    f"Could not update yt-dlp:\n{err_summary}",
                    get_yt_dlp_version(),
                )
        except Exception as exc:
            self.signals.finished.emit(
                False,
                f"Failed to execute pip update: {exc}",
                get_yt_dlp_version(),
            )