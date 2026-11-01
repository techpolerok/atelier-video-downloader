"""Settings dialog for advanced options, cookies, network proxy, and yt-dlp updates."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.downloader import UpdateYtDlpWorker, get_yt_dlp_version
from app.core.settings import AppSettings
from app.ui.theme import ThemeManager


class SettingsDialog(QDialog):
    """Modal configuration dialog for advanced yt-dlp and UI preferences."""

    log_message = Signal(str)
    version_updated = Signal(str)

    def __init__(
        self,
        settings: AppSettings,
        theme_manager: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._theme_manager = theme_manager
        self._pool = QThreadPool.globalInstance()

        self.setWindowTitle("Preferences & Advanced Settings")
        self.setMinimumWidth(540)
        self.setModal(True)

        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        """Construct the settings dialog layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        title = QLabel("Preferences & Advanced Configuration")
        title.setObjectName("SectionHeading")
        root.addWidget(title)

        # --- Appearance & Output Card ---
        general_card = QFrame(self)
        general_card.setObjectName("CardPanel")
        gen_layout = QFormLayout(general_card)
        gen_layout.setContentsMargins(16, 16, 16, 16)
        gen_layout.setSpacing(12)

        self.combo_theme = QComboBox(general_card)
        self.combo_theme.addItem("Follow System Theme", "system")
        self.combo_theme.addItem("Light (Warm Ivory)", "light")
        self.combo_theme.addItem("Dark (Deep Charcoal)", "dark")
        gen_layout.addRow("Appearance Theme:", self.combo_theme)

        dir_row = QHBoxLayout()
        self.edit_default_dir = QLineEdit(general_card)
        btn_browse = QPushButton("Browse...", general_card)
        btn_browse.clicked.connect(self._browse_folder)
        dir_row.addWidget(self.edit_default_dir, 1)
        dir_row.addWidget(btn_browse)
        gen_layout.addRow("Default Download Folder:", dir_row)

        self.edit_template = QLineEdit(general_card)
        self.edit_template.setPlaceholderText("%(title)s.%(ext)s")
        gen_layout.addRow("Filename Template:", self.edit_template)

        root.addWidget(general_card)

        # --- Authentication & Network Card ---
        adv_card = QFrame(self)
        adv_card.setObjectName("CardPanel")
        adv_layout = QFormLayout(adv_card)
        adv_layout.setContentsMargins(16, 16, 16, 16)
        adv_layout.setSpacing(12)

        self.combo_cookies = QComboBox(adv_card)
        self.combo_cookies.addItem("None (Public access only)", "")
        self.combo_cookies.addItem("Firefox", "firefox")
        self.combo_cookies.addItem("Chrome", "chrome")
        self.combo_cookies.addItem("Chromium", "chromium")
        self.combo_cookies.setToolTip(
            "Import session cookies from your local browser for age-restricted or private videos."
        )
        adv_layout.addRow("Cookies from Browser:", self.combo_cookies)

        self.edit_proxy = QLineEdit(adv_card)
        self.edit_proxy.setPlaceholderText("e.g. http://127.0.0.1:8080 or socks5://127.0.0.1:1080")
        adv_layout.addRow("Network Proxy URL:", self.edit_proxy)

        self.spin_ratelimit = QSpinBox(adv_card)
        self.spin_ratelimit.setRange(0, 100000)
        self.spin_ratelimit.setSingleStep(250)
        self.spin_ratelimit.setSuffix(" KiB/s (0 = Unlimited)")
        adv_layout.addRow("Download Rate Limit:", self.spin_ratelimit)

        root.addWidget(adv_card)

        # --- Engine Maintenance Card ---
        engine_card = QFrame(self)
        engine_card.setObjectName("CardPanel")
        eng_layout = QVBoxLayout(engine_card)
        eng_layout.setContentsMargins(16, 14, 16, 14)
        eng_layout.setSpacing(8)

        ver_row = QHBoxLayout()
        self.lbl_version = QLabel(f"Installed yt-dlp version: {get_yt_dlp_version()}")
        self.lbl_version.setStyleSheet("font-weight: 600;")
        self.btn_update_ytdlp = QPushButton("Update yt-dlp")
        self.btn_update_ytdlp.clicked.connect(self._run_ytdlp_update)
        ver_row.addWidget(self.lbl_version, 1)
        ver_row.addWidget(self.btn_update_ytdlp)
        eng_layout.addLayout(ver_row)

        self.lbl_update_status = QLabel(
            "Runs 'pip install -U yt-dlp' inside the application's Python environment."
        )
        self.lbl_update_status.setObjectName("MutedLabel")
        self.lbl_update_status.setWordWrap(True)
        eng_layout.addWidget(self.lbl_update_status)

        root.addWidget(engine_card)

        # --- Dialog Footer Buttons ---
        footer = QHBoxLayout()
        footer.addStretch(1)
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save Changes", self)
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._save_and_accept)
        footer.addWidget(btn_cancel)
        footer.addWidget(btn_save)
        root.addLayout(footer)

    def _load_values(self) -> None:
        """Populate controls from current AppSettings."""
        idx_theme = self.combo_theme.findData(self._settings.theme_mode)
        if idx_theme >= 0:
            self.combo_theme.setCurrentIndex(idx_theme)

        self.edit_default_dir.setText(self._settings.download_dir)
        self.edit_template.setText(self._settings.filename_template)

        idx_cookie = self.combo_cookies.findData(self._settings.cookies_browser)
        if idx_cookie >= 0:
            self.combo_cookies.setCurrentIndex(idx_cookie)

        self.edit_proxy.setText(self._settings.proxy_url)
        self.spin_ratelimit.setValue(self._settings.rate_limit_kib)

    def _browse_folder(self) -> None:
        """Open directory picker for the default download path."""
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Default Download Directory",
            self.edit_default_dir.text(),
        )
        if chosen:
            self.edit_default_dir.setText(chosen)

    def _run_ytdlp_update(self) -> None:
        """Launch background worker to upgrade yt-dlp via pip."""
        self.btn_update_ytdlp.setEnabled(False)
        self.lbl_update_status.setText("Updating yt-dlp via pip... Please wait.")
        worker = UpdateYtDlpWorker()
        worker.signals.log.connect(self.log_message.emit)
        worker.signals.finished.connect(self._on_update_finished)
        self._pool.start(worker)

    @Slot(bool, str, str)
    def _on_update_finished(self, success: bool, message: str, new_ver: str) -> None:
        self.btn_update_ytdlp.setEnabled(True)
        self.lbl_version.setText(f"Installed yt-dlp version: {new_ver}")
        self.lbl_update_status.setText(message)
        self.version_updated.emit(new_ver)

    def _save_and_accept(self) -> None:
        """Persist settings to QSettings and apply theme updates."""
        theme_mode = str(self.combo_theme.currentData() or "system")
        self._settings.theme_mode = theme_mode
        self._settings.download_dir = self.edit_default_dir.text()
        self._settings.filename_template = self.edit_template.text()
        self._settings.cookies_browser = str(self.combo_cookies.currentData() or "")
        self._settings.proxy_url = self.edit_proxy.text()
        self._settings.rate_limit_kib = self.spin_ratelimit.value()
        self._settings.sync()

        self._theme_manager.apply_current_theme()
        self.accept()