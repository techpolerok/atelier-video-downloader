#!/usr/bin/env python3
"""Main entry point for the Atelier YT-DLP Linux Desktop Application."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

# Ensure the project root is on sys.path when launched directly
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.theme import ThemeManager, create_app_icon


def main() -> int:
    """Initialize the Qt application, apply theming, and launch the main window."""
    # Enable high-DPI scaling policies cleanly on Qt6
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Atelier Video Archiver")
    app.setOrganizationName("AtelierDesktop")
    app.setOrganizationDomain("atelier.local")
    app.setWindowIcon(create_app_icon())

    # Keep running when minimized to system tray unless explicitly quit
    app.setQuitOnLastWindowClosed(True)

    # Load persistent user settings and apply centralized QSS theme
    settings = AppSettings()
    theme_manager = ThemeManager(app, settings)
    theme_manager.apply_current_theme()

    # Initialize and display main window
    window = MainWindow(settings=settings, theme_manager=theme_manager)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())