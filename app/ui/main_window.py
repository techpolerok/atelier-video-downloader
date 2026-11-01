"""Main window implementing the classic-modern YouTube archival interface."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QThreadPool, QUrl, Qt, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStatusBar,
    QSystemTrayIcon,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.core.downloader import (
    DownloadOptions,
    InfoFetchWorker,
    MediaInfo,
    QueueItem,
    check_ffmpeg_installed,
    format_duration,
    get_ffmpeg_install_instructions,
    get_yt_dlp_version,
)
from app.core.queue_manager import QueueManager
from app.core.settings import AppSettings
from app.ui.queue_table import QueueTableWidget
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import ThemeManager, create_app_icon, create_icon


class InfoDialog(QDialog):
    """Styled modal dialog replacing native alerts for About, Version, and Diagnostics."""

    def __init__(
        self,
        title: str,
        heading: str,
        body: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 20)
        layout.setSpacing(14)

        lbl_heading = QLabel(heading, self)
        lbl_heading.setObjectName("SectionHeading")
        layout.addWidget(lbl_heading)

        card = QFrame(self)
        card.setObjectName("CardPanel")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)

        lbl_body = QLabel(body, card)
        lbl_body.setWordWrap(True)
        lbl_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        c_layout.addWidget(lbl_body)
        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = QPushButton("Close", self)
        btn_close.setObjectName("PrimaryButton")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)


class MainWindow(QMainWindow):
    """Primary desktop window divided into URL/Info Preview, Options, and Queue Table."""

    def __init__(
        self,
        settings: AppSettings,
        theme_manager: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._theme_manager = theme_manager
        self._thread_pool = QThreadPool.globalInstance()
        self._net_manager = QNetworkAccessManager(self)
        self._net_manager.finished.connect(self._on_thumbnail_downloaded)

        self._current_media: MediaInfo | None = None
        self._queue_manager = QueueManager(
            max_concurrent=self._settings.max_concurrent_downloads,
            parent=self,
        )

        self.setWindowTitle("Atelier Video Archiver")
        self.setMinimumSize(980, 740)
        self.resize(1080, 820)

        self._setup_menus_and_toolbar()
        self._setup_central_ui()
        self._setup_status_bar()
        self._setup_tray_icon()
        self._setup_shortcuts()
        self._connect_signals()

        self._load_persisted_options()
        self._refresh_theme_icons()
        self._verify_ffmpeg_on_startup()

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------

    def _setup_menus_and_toolbar(self) -> None:
        """Create classic desktop menu bar and icon toolbar."""
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        self.act_paste = QAction("Paste URL", self)
        self.act_paste.setShortcut(QKeySequence("Ctrl+V"))
        self.act_paste.triggered.connect(self._paste_from_clipboard)
        file_menu.addAction(self.act_paste)

        self.act_fetch = QAction("Fetch Media Info", self)
        self.act_fetch.triggered.connect(self._fetch_url_info)
        file_menu.addAction(self.act_fetch)

        file_menu.addSeparator()

        self.act_quit = QAction("&Quit", self)
        self.act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_quit.triggered.connect(self.close)
        file_menu.addAction(self.act_quit)

        # Settings Menu
        settings_menu = menu_bar.addMenu("&Settings")
        self.act_preferences = QAction("&Preferences && Advanced...", self)
        self.act_preferences.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(self.act_preferences)

        self.act_toggle_theme = QAction("Toggle &Light / Dark Theme", self)
        self.act_toggle_theme.triggered.connect(self._toggle_theme)
        settings_menu.addAction(self.act_toggle_theme)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        self.act_ytdlp_version = QAction("&yt-dlp Version...", self)
        self.act_ytdlp_version.triggered.connect(self._show_version_dialog)
        help_menu.addAction(self.act_ytdlp_version)

        self.act_about = QAction("&About Atelier Archiver...", self)
        self.act_about.triggered.connect(self._show_about_dialog)
        help_menu.addAction(self.act_about)

        # Toolbar
        self.toolbar = QToolBar("Main Toolbar", self)
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.toolbar.addAction(self.act_paste)
        self.toolbar.addAction(self.act_fetch)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.act_preferences)
        self.toolbar.addAction(self.act_toggle_theme)

        self.act_toggle_log = QAction("Activity Log", self)
        self.act_toggle_log.setCheckable(True)
        self.act_toggle_log.setChecked(False)
        self.act_toggle_log.triggered.connect(self._toggle_log_panel)
        self.toolbar.addAction(self.act_toggle_log)

    def _setup_central_ui(self) -> None:
        """Assemble the 3-tier vertical layout: Top (URL+Info), Middle (Options), Bottom (Queue)."""
        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(12)

        # Optional FFmpeg missing banner (hidden when ffmpeg is installed)
        self.ffmpeg_banner = QFrame(central)
        self.ffmpeg_banner.setObjectName("WarningBanner")
        self.ffmpeg_banner.setVisible(False)
        b_layout = QHBoxLayout(self.ffmpeg_banner)
        b_layout.setContentsMargins(14, 10, 14, 10)
        self.lbl_ffmpeg_warning = QLabel(get_ffmpeg_install_instructions(), self.ffmpeg_banner)
        self.lbl_ffmpeg_warning.setWordWrap(True)
        btn_dismiss_banner = QPushButton("Dismiss", self.ffmpeg_banner)
        btn_dismiss_banner.clicked.connect(lambda: self.ffmpeg_banner.setVisible(False))
        b_layout.addWidget(self.lbl_ffmpeg_warning, 1)
        b_layout.addWidget(btn_dismiss_banner, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.ffmpeg_banner)

        # =====================================================================
        # 1. TOP SECTION: URL Input & Media Preview Card
        # =====================================================================
        top_card = QFrame(central)
        top_card.setObjectName("CardPanel")
        top_layout = QVBoxLayout(top_card)
        top_layout.setContentsMargins(16, 14, 16, 14)
        top_layout.setSpacing(12)

        # URL bar row
        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        lbl_url = QLabel("Source URL:", top_card)
        lbl_url.setObjectName("SectionHeading")

        self.edit_url = QLineEdit(top_card)
        self.edit_url.setPlaceholderText(
            "https://www.youtube.com/watch?v=... or playlist / channel URL"
        )
        self.edit_url.returnPressed.connect(self._fetch_url_info)

        self.btn_paste = QPushButton("Paste", top_card)
        self.btn_paste.setToolTip("Paste URL from clipboard (Ctrl+V)")
        self.btn_paste.clicked.connect(self._paste_from_clipboard)

        self.btn_fetch = QPushButton("Fetch Info", top_card)
        self.btn_fetch.setObjectName("PrimaryButton")
        self.btn_fetch.setToolTip("Inspect video or playlist metadata (Enter)")
        self.btn_fetch.clicked.connect(self._fetch_url_info)

        url_row.addWidget(lbl_url)
        url_row.addWidget(self.edit_url, 1)
        url_row.addWidget(self.btn_paste)
        url_row.addWidget(self.btn_fetch)
        top_layout.addLayout(url_row)

        # Media Preview Row
        preview_row = QHBoxLayout()
        preview_row.setSpacing(14)

        self.thumb_frame = QFrame(top_card)
        self.thumb_frame.setObjectName("ThumbnailFrame")
        self.thumb_frame.setFixedSize(168, 96)
        thumb_layout = QVBoxLayout(self.thumb_frame)
        thumb_layout.setContentsMargins(2, 2, 2, 2)
        self.lbl_thumbnail = QLabel(self.thumb_frame)
        self.lbl_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._draw_placeholder_thumbnail()
        thumb_layout.addWidget(self.lbl_thumbnail)
        preview_row.addWidget(self.thumb_frame, 0, Qt.AlignmentFlag.AlignTop)

        # Metadata text column
        meta_col = QVBoxLayout()
        meta_col.setSpacing(6)

        self.lbl_media_title = QLabel("Paste a YouTube link to inspect media details", top_card)
        self.lbl_media_title.setObjectName("MediaTitleLabel")
        self.lbl_media_title.setWordWrap(True)
        meta_col.addWidget(self.lbl_media_title)

        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        self.lbl_channel_badge = QLabel("Channel: —", top_card)
        self.lbl_channel_badge.setObjectName("BadgeLabel")
        self.lbl_duration_badge = QLabel("Duration: —", top_card)
        self.lbl_duration_badge.setObjectName("BadgeLabel")
        self.lbl_status_hint = QLabel("Ready", top_card)
        self.lbl_status_hint.setObjectName("MutedLabel")
        badges_row.addWidget(self.lbl_channel_badge)
        badges_row.addWidget(self.lbl_duration_badge)
        badges_row.addWidget(self.lbl_status_hint, 1)
        meta_col.addLayout(badges_row)
        meta_col.addStretch(1)

        preview_row.addLayout(meta_col, 1)

        # Playlist checklist widget (visible only when a playlist/channel is loaded)
        self.playlist_container = QWidget(top_card)
        self.playlist_container.setVisible(False)
        pl_layout = QVBoxLayout(self.playlist_container)
        pl_layout.setContentsMargins(0, 0, 0, 0)
        pl_layout.setSpacing(4)

        pl_header = QHBoxLayout()
        self.lbl_playlist_count = QLabel("Playlist Videos:", self.playlist_container)
        self.lbl_playlist_count.setStyleSheet("font-weight: 600; font-size: 12px;")
        btn_sel_all = QPushButton("Select All", self.playlist_container)
        btn_sel_all.setObjectName("TableActionButton")
        btn_sel_all.clicked.connect(lambda: self._set_all_playlist_checks(Qt.CheckState.Checked))
        btn_sel_none = QPushButton("Select None", self.playlist_container)
        btn_sel_none.setObjectName("TableActionButton")
        btn_sel_none.clicked.connect(lambda: self._set_all_playlist_checks(Qt.CheckState.Unchecked))
        pl_header.addWidget(self.lbl_playlist_count, 1)
        pl_header.addWidget(btn_sel_all)
        pl_header.addWidget(btn_sel_none)
        pl_layout.addLayout(pl_header)

        self.list_playlist = QListWidget(self.playlist_container)
        self.list_playlist.setFixedHeight(92)
        pl_layout.addWidget(self.list_playlist)

        preview_row.addWidget(self.playlist_container, 1)
        top_layout.addLayout(preview_row)

        root.addWidget(top_card)

        # =====================================================================
        # 2. MIDDLE SECTION: Format Selection & Output Settings
        # =====================================================================
        mid_card = QFrame(central)
        mid_card.setObjectName("CardPanel")
        mid_grid = QGridLayout(mid_card)
        mid_grid.setContentsMargins(16, 14, 16, 14)
        mid_grid.setHorizontalSpacing(18)
        mid_grid.setVerticalSpacing(10)

        # Row 0: Mode Selector + Format Dropdowns
        mode_box = QHBoxLayout()
        mode_box.setSpacing(12)
        lbl_mode = QLabel("Format Mode:", mid_card)
        lbl_mode.setObjectName("SectionHeading")
        self.radio_video = QRadioButton("Video + Audio", mid_card)
        self.radio_audio = QRadioButton("Audio Only", mid_card)
        self.radio_video.setChecked(True)
        self.radio_video.toggled.connect(self._on_mode_toggled)
        mode_box.addWidget(lbl_mode)
        mode_box.addWidget(self.radio_video)
        mode_box.addWidget(self.radio_audio)
        mode_box.addStretch(1)
        mid_grid.addLayout(mode_box, 0, 0, 1, 2)

        # Video Format Stack
        self.video_opts_widget = QWidget(mid_card)
        v_layout = QHBoxLayout(self.video_opts_widget)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(10)
        v_layout.addWidget(QLabel("Resolution:"))
        self.combo_resolution = QComboBox(self.video_opts_widget)
        self.combo_resolution.addItems(
            ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]
        )
        v_layout.addWidget(self.combo_resolution)
        v_layout.addWidget(QLabel("Container:"))
        self.combo_container = QComboBox(self.video_opts_widget)
        self.combo_container.addItems(["mp4", "mkv", "webm"])
        v_layout.addWidget(self.combo_container)
        v_layout.addStretch(1)
        mid_grid.addWidget(self.video_opts_widget, 0, 2, 1, 2)

        # Audio Format Stack
        self.audio_opts_widget = QWidget(mid_card)
        self.audio_opts_widget.setVisible(False)
        a_layout = QHBoxLayout(self.audio_opts_widget)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.setSpacing(10)
        a_layout.addWidget(QLabel("Audio Format:"))
        self.combo_audio_fmt = QComboBox(self.audio_opts_widget)
        self.combo_audio_fmt.addItems(["mp3", "m4a", "opus", "flac", "wav"])
        self.combo_audio_fmt.currentTextChanged.connect(self._on_audio_format_changed)
        a_layout.addWidget(self.combo_audio_fmt)
        a_layout.addWidget(QLabel("Bitrate:"))
        self.combo_audio_quality = QComboBox(self.audio_opts_widget)
        for kbps in ("128", "192", "256", "320"):
            self.combo_audio_quality.addItem(f"{kbps} kbps", kbps)
        a_layout.addWidget(self.combo_audio_quality)
        a_layout.addStretch(1)
        mid_grid.addWidget(self.audio_opts_widget, 0, 2, 1, 2)

        # Row 1: Post-processing & Subtitles Checkboxes
        opts_row = QHBoxLayout()
        opts_row.setSpacing(16)
        self.chk_embed_thumb = QCheckBox("Embed Thumbnail", mid_card)
        self.chk_embed_meta = QCheckBox("Embed Metadata", mid_card)
        self.chk_dl_subs = QCheckBox("Download Subtitles:", mid_card)
        self.chk_dl_subs.toggled.connect(self._on_subtitles_toggled)

        self.combo_sub_lang = QComboBox(mid_card)
        for label, code in (
            ("English (en)", "en"),
            ("Spanish (es)", "es"),
            ("French (fr)", "fr"),
            ("German (de)", "de"),
            ("Portuguese (pt)", "pt"),
            ("Italian (it)", "it"),
            ("Japanese (ja)", "ja"),
            ("Korean (ko)", "ko"),
            ("Chinese (zh-Hans)", "zh-Hans"),
            ("All Languages (all)", "all"),
        ):
            self.combo_sub_lang.addItem(label, code)
        self.combo_sub_lang.setEditable(True)

        self.chk_embed_subs = QCheckBox("Embed Subtitles", mid_card)

        opts_row.addWidget(self.chk_embed_thumb)
        opts_row.addWidget(self.chk_embed_meta)
        opts_row.addWidget(self.chk_dl_subs)
        opts_row.addWidget(self.combo_sub_lang)
        opts_row.addWidget(self.chk_embed_subs)
        opts_row.addStretch(1)
        mid_grid.addLayout(opts_row, 1, 0, 1, 4)

        # Row 2: Output Folder, Filename Template, and Add to Queue Button
        out_row = QHBoxLayout()
        out_row.setSpacing(10)

        out_row.addWidget(QLabel("Save To:"))
        self.edit_download_dir = QLineEdit(mid_card)
        btn_pick_dir = QPushButton("Folder...", mid_card)
        btn_pick_dir.clicked.connect(self._pick_download_folder)
        out_row.addWidget(self.edit_download_dir, 2)
        out_row.addWidget(btn_pick_dir)

        out_row.addWidget(QLabel("Template:"))
        self.edit_filename_tpl = QLineEdit(mid_card)
        self.edit_filename_tpl.setPlaceholderText("%(title)s.%(ext)s")
        out_row.addWidget(self.edit_filename_tpl, 1)

        self.btn_add_queue = QPushButton("Add to Download Queue", mid_card)
        self.btn_add_queue.setObjectName("PrimaryButton")
        self.btn_add_queue.clicked.connect(self._enqueue_current_selection)
        out_row.addWidget(self.btn_add_queue)

        mid_grid.addLayout(out_row, 2, 0, 1, 4)

        root.addWidget(mid_card)

        # =====================================================================
        # 3. BOTTOM SECTION: Download Queue & Collapsible Log Panel
        # =====================================================================
        queue_card = QFrame(central)
        queue_card.setObjectName("CardPanel")
        q_layout = QVBoxLayout(queue_card)
        q_layout.setContentsMargins(16, 14, 16, 14)
        q_layout.setSpacing(10)

        q_header = QHBoxLayout()
        lbl_q_title = QLabel("Download Queue", queue_card)
        lbl_q_title.setObjectName("SectionHeading")
        q_header.addWidget(lbl_q_title)
        q_header.addStretch(1)

        q_header.addWidget(QLabel("Concurrent Downloads:"))
        self.spin_concurrent = QSpinBox(queue_card)
        self.spin_concurrent.setRange(1, 5)
        self.spin_concurrent.setValue(self._settings.max_concurrent_downloads)
        self.spin_concurrent.valueChanged.connect(self._on_concurrent_changed)
        q_header.addWidget(self.spin_concurrent)

        self.btn_clear_finished = QPushButton("Clear Finished", queue_card)
        self.btn_clear_finished.clicked.connect(self._clear_finished_items)
        q_header.addWidget(self.btn_clear_finished)

        self.btn_toggle_log = QPushButton("Show Log", queue_card)
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.toggled.connect(self._toggle_log_panel)
        q_header.addWidget(self.btn_toggle_log)

        q_layout.addLayout(q_header)

        self.queue_table = QueueTableWidget(queue_card)
        q_layout.addWidget(self.queue_table, 1)

        # Collapsible Log Output Panel
        self.log_container = QWidget(queue_card)
        self.log_container.setVisible(False)
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.setSpacing(6)

        log_header = QHBoxLayout()
        lbl_log = QLabel("yt-dlp Engine Output Log", self.log_container)
        lbl_log.setStyleSheet("font-weight: 600; font-size: 12px;")
        btn_clear_log = QPushButton("Clear Log", self.log_container)
        btn_clear_log.setObjectName("TableActionButton")
        btn_clear_log.clicked.connect(lambda: self.log_edit.clear())
        log_header.addWidget(lbl_log, 1)
        log_header.addWidget(btn_clear_log)
        log_layout.addLayout(log_header)

        self.log_edit = QPlainTextEdit(self.log_container)
        self.log_edit.setObjectName("LogPanel")
        self.log_edit.setReadOnly(True)
        self.log_edit.setFixedHeight(130)
        log_layout.addWidget(self.log_edit)

        q_layout.addWidget(self.log_container)
        root.addWidget(queue_card, 1)

    def _setup_status_bar(self) -> None:
        """Create classic bottom status bar with yt-dlp version indicator."""
        status = QStatusBar(self)
        self.setStatusBar(status)
        self.lbl_status_message = QLabel("Ready to archive media.")
        self.lbl_engine_badge = QLabel(f"yt-dlp {get_yt_dlp_version()}")
        self.lbl_engine_badge.setObjectName("MutedLabel")
        status.addWidget(self.lbl_status_message, 1)
        status.addPermanentWidget(self.lbl_engine_badge)

    def _setup_tray_icon(self) -> None:
        """Initialize system tray icon with menu and desktop notification support."""
        self.tray_icon = QSystemTrayIcon(create_app_icon(), self)
        self.tray_icon.setToolTip("Atelier Video Archiver")

        tray_menu = QMenu(self)
        act_show = QAction("Show Window", self)
        act_show.triggered.connect(self._restore_from_tray)
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        tray_menu.addAction(act_show)
        tray_menu.addSeparator()
        tray_menu.addAction(act_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    def _setup_shortcuts(self) -> None:
        """Register additional keyboard shortcuts."""
        sc_return = QShortcut(QKeySequence(Qt.Key.Key_Return), self.edit_url)
        sc_return.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_return.activated.connect(self._fetch_url_info)

    def _connect_signals(self) -> None:
        """Wire QueueManager, QueueTableWidget, and ThemeManager signals."""
        self._queue_manager.item_added.connect(self.queue_table.add_queue_item)
        self._queue_manager.item_updated.connect(self.queue_table.update_queue_item)
        self._queue_manager.item_removed.connect(self.queue_table.remove_queue_item)
        self._queue_manager.item_completed.connect(self._on_item_completed)
        self._queue_manager.log_message.connect(self._append_log)

        self.queue_table.start_resume_requested.connect(
            self._queue_manager.start_or_resume_item
        )
        self.queue_table.pause_requested.connect(self._queue_manager.pause_item)
        self.queue_table.cancel_requested.connect(self._queue_manager.cancel_item)
        self.queue_table.open_folder_requested.connect(self._open_item_folder)

        self._theme_manager.theme_changed.connect(self._on_theme_changed)

    # -------------------------------------------------------------------------
    # State Persistence & Diagnostics
    # -------------------------------------------------------------------------

    def _load_persisted_options(self) -> None:
        """Populate format and output controls from saved QSettings."""
        is_audio = self._settings.media_mode == "audio"
        self.radio_audio.setChecked(is_audio)
        self.radio_video.setChecked(not is_audio)
        self._on_mode_toggled()

        idx_res = self.combo_resolution.findText(self._settings.video_resolution)
        if idx_res >= 0:
            self.combo_resolution.setCurrentIndex(idx_res)

        idx_cont = self.combo_container.findText(self._settings.video_container)
        if idx_cont >= 0:
            self.combo_container.setCurrentIndex(idx_cont)

        idx_afmt = self.combo_audio_fmt.findText(self._settings.audio_format)
        if idx_afmt >= 0:
            self.combo_audio_fmt.setCurrentIndex(idx_afmt)

        idx_aq = self.combo_audio_quality.findData(self._settings.audio_quality)
        if idx_aq >= 0:
            self.combo_audio_quality.setCurrentIndex(idx_aq)

        self.chk_embed_thumb.setChecked(self._settings.embed_thumbnail)
        self.chk_embed_meta.setChecked(self._settings.embed_metadata)
        self.chk_dl_subs.setChecked(self._settings.download_subtitles)

        idx_sub = self.combo_sub_lang.findData(self._settings.subtitle_language)
        if idx_sub >= 0:
            self.combo_sub_lang.setCurrentIndex(idx_sub)
        else:
            self.combo_sub_lang.setEditText(self._settings.subtitle_language)

        self.chk_embed_subs.setChecked(self._settings.embed_subtitles)
        self._on_subtitles_toggled(self.chk_dl_subs.isChecked())

        self.edit_download_dir.setText(self._settings.download_dir)
        self.edit_filename_tpl.setText(self._settings.filename_template)

    def _save_current_options_to_settings(self) -> DownloadOptions:
        """Persist current UI form controls to AppSettings and return a DownloadOptions snapshot."""
        mode = "audio" if self.radio_audio.isChecked() else "video"
        res = self.combo_resolution.currentText()
        cont = self.combo_container.currentText()
        afmt = self.combo_audio_fmt.currentText()
        aqual = str(self.combo_audio_quality.currentData() or "192")
        sub_lang = str(
            self.combo_sub_lang.currentData()
            or self.combo_sub_lang.currentText().strip()
            or "en"
        )
        dl_dir = self.edit_download_dir.text().strip() or self._settings.download_dir
        tpl = self.edit_filename_tpl.text().strip() or "%(title)s.%(ext)s"

        self._settings.media_mode = mode
        self._settings.video_resolution = res
        self._settings.video_container = cont
        self._settings.audio_format = afmt
        self._settings.audio_quality = aqual
        self._settings.embed_thumbnail = self.chk_embed_thumb.isChecked()
        self._settings.embed_metadata = self.chk_embed_meta.isChecked()
        self._settings.download_subtitles = self.chk_dl_subs.isChecked()
        self._settings.subtitle_language = sub_lang
        self._settings.embed_subtitles = self.chk_embed_subs.isChecked()
        self._settings.download_dir = dl_dir
        self._settings.filename_template = tpl
        self._settings.sync()

        return DownloadOptions(
            media_mode=mode,
            video_resolution=res,
            video_container=cont,
            audio_format=afmt,
            audio_quality=aqual,
            embed_thumbnail=self.chk_embed_thumb.isChecked(),
            embed_metadata=self.chk_embed_meta.isChecked(),
            download_subtitles=self.chk_dl_subs.isChecked(),
            subtitle_language=sub_lang,
            embed_subtitles=self.chk_embed_subs.isChecked(),
            download_dir=dl_dir,
            filename_template=tpl,
            cookies_browser=self._settings.cookies_browser,
            proxy_url=self._settings.proxy_url,
            rate_limit_kib=self._settings.rate_limit_kib,
        )

    def _verify_ffmpeg_on_startup(self) -> None:
        """Check whether ffmpeg is installed and show distro instructions if missing."""
        if not check_ffmpeg_installed():
            self.ffmpeg_banner.setVisible(True)
            self._append_log("[WARN] FFmpeg binary not found on system PATH.")
        else:
            self._append_log("[INFO] FFmpeg detected on system PATH.")

    # -------------------------------------------------------------------------
    # User Actions & Slots
    # -------------------------------------------------------------------------

    def _paste_from_clipboard(self) -> None:
        """Read text from the system clipboard into the URL field."""
        clip_text = QApplication.clipboard().text().strip()
        if clip_text:
            self.edit_url.setText(clip_text)
            self.edit_url.setFocus()
            self._set_status("Pasted URL from clipboard.")

    def _fetch_url_info(self) -> None:
        """Start an asynchronous InfoFetchWorker for the entered URL."""
        url = self.edit_url.text().strip()
        if not url:
            self._set_status("Please enter or paste a YouTube URL first.")
            self.edit_url.setFocus()
            return

        self.btn_fetch.setEnabled(False)
        self.btn_fetch.setText("Fetching...")
        self.lbl_status_hint.setText("Inspecting URL via yt-dlp...")
        self._set_status(f"Fetching metadata for {url}...")

        worker = InfoFetchWorker(
            url=url,
            cookies_browser=self._settings.cookies_browser,
            proxy_url=self._settings.proxy_url,
        )
        worker.signals.finished.connect(self._on_info_fetched)
        worker.signals.error.connect(self._on_info_error)
        worker.signals.log.connect(self._append_log)
        self._thread_pool.start(worker)

    @Slot(object)
    def _on_info_fetched(self, info: MediaInfo) -> None:
        """Display fetched video or playlist metadata in the preview panel."""
        self.btn_fetch.setEnabled(True)
        self.btn_fetch.setText("Fetch Info")
        self._current_media = info

        self.lbl_media_title.setText(info.title)
        self.lbl_channel_badge.setText(f"Channel: {info.channel}")

        if info.is_playlist:
            self.lbl_duration_badge.setText(f"Playlist: {len(info.entries)} videos")
            self.lbl_status_hint.setText("Select playlist items below to queue")
            self.playlist_container.setVisible(True)
            self.list_playlist.clear()
            for entry in info.entries:
                dur_str = format_duration(entry.duration)
                item = QListWidgetItem(
                    f"{entry.index:02d}. {entry.title}  [{dur_str}]"
                )
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setData(Qt.ItemDataRole.UserRole, entry)
                self.list_playlist.addItem(item)
            self.lbl_playlist_count.setText(f"Playlist Videos ({len(info.entries)}):")
        else:
            self.lbl_duration_badge.setText(
                f"Duration: {format_duration(info.duration)}"
            )
            self.lbl_status_hint.setText("Ready to download")
            self.playlist_container.setVisible(False)
            self.list_playlist.clear()

        if info.thumbnail_url:
            req = QNetworkRequest(QUrl(info.thumbnail_url))
            self._net_manager.get(req)
        else:
            self._draw_placeholder_thumbnail()

        self._set_status(f"Loaded metadata for '{info.title}'.")

    @Slot(str)
    def _on_info_error(self, error_msg: str) -> None:
        """Handle metadata extraction failure gracefully."""
        self.btn_fetch.setEnabled(True)
        self.btn_fetch.setText("Fetch Info")
        self.lbl_status_hint.setText(f"Error: {error_msg}")
        self._set_status(f"Metadata error: {error_msg}")
        dlg = InfoDialog(
            title="Could Not Fetch Media Info",
            heading="Unable to Inspect URL",
            body=error_msg,
            parent=self,
        )
        dlg.exec()

    @Slot(QNetworkReply)
    def _on_thumbnail_downloaded(self, reply: QNetworkReply) -> None:
        """Render the downloaded video thumbnail into the preview frame."""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                scaled = pixmap.scaled(
                    self.lbl_thumbnail.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.lbl_thumbnail.setPixmap(scaled)
                reply.deleteLater()
                return
        self._draw_placeholder_thumbnail()
        reply.deleteLater()

    def _draw_placeholder_thumbnail(self) -> None:
        """Render a clean vector placeholder when no thumbnail is loaded."""
        pix = QPixmap(162, 90)
        is_dark = self._theme_manager.resolve_effective_mode() == "dark"
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPixmap(65, 29, create_icon("play", is_dark).pixmap(32, 32))
        painter.end()
        self.lbl_thumbnail.setPixmap(pix)

    def _set_all_playlist_checks(self, state: Qt.CheckState) -> None:
        """Check or uncheck all items in the playlist preview list."""
        for i in range(self.list_playlist.count()):
            item = self.list_playlist.item(i)
            if item:
                item.setCheckState(state)

    def _enqueue_current_selection(self) -> None:
        """Add the current URL or checked playlist items to the download queue."""
        url = self.edit_url.text().strip()
        if not url and not self._current_media:
            self._set_status("Enter a valid YouTube URL before adding to the queue.")
            self.edit_url.setFocus()
            return

        options = self._save_current_options_to_settings()

        # If a playlist is currently loaded and matches the input URL
        if (
            self._current_media
            and self._current_media.is_playlist
            and self.list_playlist.count() > 0
        ):
            added_count = 0
            for i in range(self.list_playlist.count()):
                list_item = self.list_playlist.item(i)
                if list_item and list_item.checkState() == Qt.CheckState.Checked:
                    entry = list_item.data(Qt.ItemDataRole.UserRole)
                    if entry:
                        self._queue_manager.add_item(
                            url=entry.url,
                            title=entry.title,
                            options=options,
                            auto_start=True,
                        )
                        added_count += 1
            if added_count == 0:
                self._set_status("No playlist videos were checked.")
            else:
                self._set_status(f"Added {added_count} playlist video(s) to the queue.")
            return

        # Single video
        title = (
            self._current_media.title
            if self._current_media and self._current_media.url
            else url
        )
        target_url = self._current_media.url if self._current_media else url
        self._queue_manager.add_item(
            url=target_url,
            title=title,
            options=options,
            auto_start=True,
        )
        self._set_status(f"Queued '{title}' for download.")

    def _on_mode_toggled(self) -> None:
        """Switch visible controls between Video and Audio-Only modes."""
        is_video = self.radio_video.isChecked()
        self.video_opts_widget.setVisible(is_video)
        self.audio_opts_widget.setVisible(not is_video)
        self.chk_embed_subs.setEnabled(is_video and self.chk_dl_subs.isChecked())

    def _on_audio_format_changed(self, fmt: str) -> None:
        """Disable lossy bitrate selection when lossless FLAC or WAV is chosen."""
        self.combo_audio_quality.setEnabled(fmt not in ("flac", "wav"))

    def _on_subtitles_toggled(self, checked: bool) -> None:
        """Enable or disable subtitle language and embed controls."""
        self.combo_sub_lang.setEnabled(checked)
        self.chk_embed_subs.setEnabled(checked and self.radio_video.isChecked())

    def _pick_download_folder(self) -> None:
        """Open native directory chooser for the output folder."""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Download Folder",
            self.edit_download_dir.text() or str(Path.home()),
        )
        if selected:
            self.edit_download_dir.setText(selected)
            self._settings.download_dir = selected
            self._settings.sync()

    def _on_concurrent_changed(self, count: int) -> None:
        """Update concurrency limit in QueueManager and persist in QSettings."""
        self._settings.max_concurrent_downloads = count
        self._settings.sync()
        self._queue_manager.set_max_concurrent(count)
        self._set_status(f"Concurrent downloads limit set to {count}.")

    def _clear_finished_items(self) -> None:
        """Remove completed and canceled downloads from the queue table."""
        removed = self._queue_manager.clear_finished()
        self._set_status(f"Cleared {removed} finished item(s) from the queue.")

    def _toggle_log_panel(self, checked: bool) -> None:
        """Expand or collapse the bottom yt-dlp log panel."""
        self.log_container.setVisible(checked)
        self.btn_toggle_log.setChecked(checked)
        self.btn_toggle_log.setText("Hide Log" if checked else "Show Log")
        self.act_toggle_log.setChecked(checked)

    @Slot(str)
    def _append_log(self, line: str) -> None:
        """Append a formatted line to the collapsible log viewer."""
        self.log_edit.appendPlainText(line)

    @Slot(object)
    def _on_item_completed(self, item: QueueItem) -> None:
        """Notify the user via status bar and system tray when an item finishes."""
        self._set_status(f"Completed: {item.title}")
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "Download Complete",
                f"Finished archiving '{item.title}'",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    @Slot(str)
    def _open_item_folder(self, item_id: str) -> None:
        """Open the folder containing a finished queue item in the Linux file manager."""
        item = self._queue_manager.get_item(item_id)
        if not item:
            return
        folder_path = Path(item.output_dir or item.options.download_dir)
        if item.output_filepath:
            candidate = Path(item.output_filepath).parent
            if candidate.exists():
                folder_path = candidate
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))

    def _open_settings_dialog(self) -> None:
        """Launch the Preferences & Advanced Settings modal dialog."""
        dlg = SettingsDialog(self._settings, self._theme_manager, self)
        dlg.log_message.connect(self._append_log)
        dlg.version_updated.connect(
            lambda ver: self.lbl_engine_badge.setText(f"yt-dlp {ver}")
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.edit_download_dir.setText(self._settings.download_dir)
            self.edit_filename_tpl.setText(self._settings.filename_template)
            self._set_status("Settings saved.")

    def _toggle_theme(self) -> None:
        """Toggle between Light and Dark themes."""
        mode = self._theme_manager.toggle_light_dark()
        self._set_status(f"Switched to {mode.capitalize()} theme.")

    @Slot(str)
    def _on_theme_changed(self, _palette_name: str) -> None:
        """Refresh custom QPainter icons when the theme changes."""
        self._refresh_theme_icons()

    def _refresh_theme_icons(self) -> None:
        """Update toolbar, button, and table icons to match light/dark surface contrast."""
        is_dark = self._theme_manager.resolve_effective_mode() == "dark"
        self.act_paste.setIcon(create_icon("paste", is_dark))
        self.act_fetch.setIcon(create_icon("fetch", is_dark))
        self.act_preferences.setIcon(create_icon("settings", is_dark))
        self.act_toggle_theme.setIcon(create_icon("theme", is_dark))
        self.act_toggle_log.setIcon(create_icon("log", is_dark))

        self.btn_paste.setIcon(create_icon("paste", is_dark))
        self.btn_fetch.setIcon(create_icon("fetch", True))
        self.btn_add_queue.setIcon(create_icon("download", True))
        self.btn_clear_finished.setIcon(create_icon("clear", is_dark))
        self.queue_table.refresh_icons(is_dark)

        if self._current_media is None or not self._current_media.thumbnail_url:
            self._draw_placeholder_thumbnail()

    def _show_version_dialog(self) -> None:
        """Show current yt-dlp and FFmpeg status in a styled dialog."""
        ffmpeg_ok = "Installed and available on PATH" if check_ffmpeg_installed() else "Not found on PATH"
        body = (
            f"yt-dlp Python Library Version:  {get_yt_dlp_version()}\n"
            f"FFmpeg Binary Status:           {ffmpeg_ok}\n\n"
            "You can update yt-dlp at any time via Settings → Preferences & Advanced."
        )
        dlg = InfoDialog("Engine Version", "yt-dlp & FFmpeg Status", body, self)
        dlg.exec()

    def _show_about_dialog(self) -> None:
        """Display the About dialog."""
        body = (
            "Atelier Video Archiver is a native Linux desktop utility crafted with "
            "PySide6 (Qt6) and the yt-dlp Python library.\n\n"
            "Features:\n"
            "• Single videos, playlists, and channels with selective queueing\n"
            "• High-resolution video merging and lossless/lossy audio extraction\n"
            "• Non-blocking multi-threaded queue with Pause, Resume, and Cancel\n"
            "• Browser cookie authentication, proxy support, and live engine logs"
        )
        dlg = InfoDialog(
            "About Atelier Video Archiver",
            "Atelier Video Archiver",
            body,
            self,
        )
        dlg.exec()

    def _restore_from_tray(self) -> None:
        """Bring the main window to the front."""
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore_from_tray()

    def _set_status(self, text: str) -> None:
        """Update the bottom status bar text."""
        self.lbl_status_message.setText(text)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Save current form state and gracefully stop worker threads on exit."""
        self._save_current_options_to_settings()
        self._queue_manager.shutdown()
        self.tray_icon.hide()
        super().closeEvent(event)