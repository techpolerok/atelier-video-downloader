"""Centralized QSS stylesheet, color palettes, and vector iconography."""

from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication

from app.core.settings import AppSettings


@dataclass(frozen=True)
class ThemePalette:
    """Semantic color tokens for the classic-modern visual identity."""

    name: str
    bg_window: str
    bg_panel: str
    bg_elevated: str
    bg_input: str
    bg_alt_row: str
    bg_hover: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_accent: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    border_subtle: str
    border_strong: str
    status_success: str
    status_warning: str
    status_danger: str


LIGHT_PALETTE = ThemePalette(
    name="light",
    bg_window="#F5F2E9",       # Warm Ivory
    bg_panel="#FCFBF7",        # Crisp Alabaster
    bg_elevated="#EFECE1",     # Soft Cream
    bg_input="#FFFFFF",        # Pure White Input
    bg_alt_row="#F7F4EC",      # Subtle Table Alternating Row
    bg_hover="#EAE5D7",        # Warm Hover Surface
    text_primary="#1E201D",    # Deep Charcoal
    text_secondary="#4A4D47",  # Slate Charcoal
    text_muted="#767871",      # Muted Warm Gray
    text_on_accent="#FAF8F5",  # Ivory on Burgundy
    accent="#7A202E",          # Classic Deep Burgundy
    accent_hover="#8F2737",    # Rich Burgundy Hover
    accent_pressed="#611823",  # Deep Pressed Burgundy
    accent_soft="#F2E4E6",     # Soft Burgundy Tint
    border_subtle="#DCD7C8",   # Engraved Warm Stone Border
    border_strong="#BFB8A6",   # Defined Panel Border
    status_success="#235D3A",  # Forest Green
    status_warning="#9C6514",  # Warm Ochre
    status_danger="#9E2A2B",   # Crimson
)

DARK_PALETTE = ThemePalette(
    name="dark",
    bg_window="#181816",       # Deep Warm Charcoal
    bg_panel="#22221F",        # Elevated Charcoal Panel
    bg_elevated="#2B2B27",     # Secondary Surface
    bg_input="#141412",        # Engraved Dark Input
    bg_alt_row="#1D1D1A",      # Subtle Dark Table Row
    bg_hover="#33332E",        # Warm Charcoal Hover
    text_primary="#EAE6DF",    # Warm Off-White
    text_secondary="#B8B4AC",  # Muted Parchment
    text_muted="#827F78",      # Dim Stone
    text_on_accent="#FAF8F5",  # Crisp Off-White
    accent="#9E2E40",          # Luminous Deep Burgundy
    accent_hover="#B5374B",    # Highlight Burgundy
    accent_pressed="#7D2231",  # Pressed Burgundy
    accent_soft="#361E22",     # Dark Burgundy Tint
    border_subtle="#34332E",   # Subtle Dark Separator
    border_strong="#4A4842",   # Defined Dark Border
    status_success="#3B8EA5",  # Muted Teal-Green
    status_warning="#D99B26",  # Warm Amber
    status_danger="#D14949",   # Soft Vermilion
)


def build_stylesheet(p: ThemePalette) -> str:
    """Generate the application-wide Qt Style Sheet (QSS) for the given palette."""
    return f"""
    /* --- Global Defaults --- */
    QWidget {{
        background-color: {p.bg_window};
        color: {p.text_primary};
        font-family: "Inter", "Noto Sans", "Cantarell", "DejaVu Sans", sans-serif;
        font-size: 13px;
        selection-background-color: {p.accent};
        selection-color: {p.text_on_accent};
    }}

    QMainWindow, QDialog {{
        background-color: {p.bg_window};
    }}

    /* --- Menu Bar & Menus --- */
    QMenuBar {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border-bottom: 1px solid {p.border_subtle};
        padding: 3px 8px;
        font-weight: 500;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 5px 10px;
        border-radius: 6px;
    }}
    QMenuBar::item:selected {{
        background-color: {p.bg_hover};
    }}
    QMenu {{
        background-color: {p.bg_panel};
        color: {p.text_primary};
        border: 1px solid {p.border_strong};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 12px;
        border-radius: 5px;
    }}
    QMenu::item:selected {{
        background-color: {p.accent};
        color: {p.text_on_accent};
    }}
    QMenu::separator {{
        height: 1px;
        background: {p.border_subtle};
        margin: 4px 8px;
    }}

    /* --- ToolBar --- */
    QToolBar {{
        background-color: {p.bg_panel};
        border-bottom: 1px solid {p.border_subtle};
        padding: 6px 12px;
        spacing: 8px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {p.text_primary};
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 6px 10px;
        font-weight: 500;
    }}
    QToolButton:hover {{
        background-color: {p.bg_hover};
        border: 1px solid {p.border_subtle};
    }}
    QToolButton:pressed {{
        background-color: {p.bg_elevated};
    }}

    /* --- Classic Engraved / Raised Panels --- */
    QFrame#CardPanel {{
        background-color: {p.bg_panel};
        border: 1px solid {p.border_subtle};
        border-radius: 10px;
    }}
    QFrame#WarningBanner {{
        background-color: {p.accent_soft};
        border: 1px solid {p.accent};
        border-radius: 8px;
    }}
    QFrame#ThumbnailFrame {{
        background-color: {p.bg_elevated};
        border: 1px solid {p.border_strong};
        border-radius: 8px;
    }}

    /* --- Typography Hierarchy --- */
    QLabel {{
        background: transparent;
    }}
    QLabel#AppHeaderTitle {{
        font-family: "Playfair Display", "Lora", "Source Serif 4", "Noto Serif", "DejaVu Serif", serif;
        font-size: 19px;
        font-weight: 700;
        color: {p.text_primary};
    }}
    QLabel#SectionHeading {{
        font-family: "Playfair Display", "Lora", "Source Serif 4", "Noto Serif", "DejaVu Serif", serif;
        font-size: 15px;
        font-weight: 700;
        color: {p.text_primary};
    }}
    QLabel#MediaTitleLabel {{
        font-family: "Playfair Display", "Lora", "Source Serif 4", "Noto Serif", "DejaVu Serif", serif;
        font-size: 16px;
        font-weight: 700;
        color: {p.text_primary};
    }}
    QLabel#MutedLabel {{
        color: {p.text_secondary};
        font-size: 12px;
    }}
    QLabel#BadgeLabel {{
        background-color: {p.bg_elevated};
        color: {p.text_secondary};
        border: 1px solid {p.border_subtle};
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
    }}

    /* --- Inputs & Dropdowns --- */
    QLineEdit, QSpinBox, QComboBox {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border_strong};
        border-radius: 8px;
        padding: 7px 11px;
        min-height: 20px;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {p.accent};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
        background-color: {p.bg_elevated};
        color: {p.text_muted};
        border-color: {p.border_subtle};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p.bg_panel};
        color: {p.text_primary};
        border: 1px solid {p.border_strong};
        border-radius: 6px;
        selection-background-color: {p.accent};
        selection-color: {p.text_on_accent};
        padding: 4px;
    }}

    /* --- Buttons --- */
    QPushButton {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border: 1px solid {p.border_strong};
        border-radius: 8px;
        padding: 7px 14px;
        font-weight: 600;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background-color: {p.bg_hover};
        border-color: {p.text_muted};
    }}
    QPushButton:pressed {{
        background-color: {p.border_subtle};
    }}
    QPushButton:disabled {{
        background-color: {p.bg_window};
        color: {p.text_muted};
        border-color: {p.border_subtle};
    }}

    QPushButton#PrimaryButton {{
        background-color: {p.accent};
        color: {p.text_on_accent};
        border: 1px solid {p.accent_pressed};
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: {p.accent_hover};
    }}
    QPushButton#PrimaryButton:pressed {{
        background-color: {p.accent_pressed};
    }}
    QPushButton#PrimaryButton:disabled {{
        background-color: {p.border_subtle};
        color: {p.text_muted};
        border-color: {p.border_subtle};
    }}

    QPushButton#TableActionButton {{
        padding: 4px 8px;
        min-height: 16px;
        border-radius: 6px;
        font-size: 12px;
    }}

    /* --- Checkboxes & RadioButtons --- */
    QCheckBox, QRadioButton {{
        background: transparent;
        spacing: 7px;
        color: {p.text_primary};
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {p.border_strong};
        background-color: {p.bg_input};
    }}
    QCheckBox::indicator {{
        border-radius: 4px;
    }}
    QRadioButton::indicator {{
        border-radius: 8px;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {p.accent};
        border-color: {p.accent};
    }}

    /* --- Tables & Lists --- */
    QTableWidget, QListWidget {{
        background-color: {p.bg_panel};
        alternate-background-color: {p.bg_alt_row};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
        gridline-color: {p.border_subtle};
        outline: none;
    }}
    QHeaderView::section {{
        background-color: {p.bg_elevated};
        color: {p.text_secondary};
        border: none;
        border-bottom: 1px solid {p.border_strong};
        border-right: 1px solid {p.border_subtle};
        padding: 7px 10px;
        font-weight: 600;
        font-size: 12px;
    }}
    QTableWidget::item, QListWidget::item {{
        padding: 5px 8px;
    }}
    QTableWidget::item:selected, QListWidget::item:selected {{
        background-color: {p.accent_soft};
        color: {p.text_primary};
    }}

    /* --- Progress Bar --- */
    QProgressBar {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        border-radius: 6px;
        text-align: center;
        font-size: 11px;
        font-weight: 600;
        min-height: 16px;
        max-height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {p.accent};
        border-radius: 5px;
    }}

    /* --- Log Output Panel --- */
    QPlainTextEdit#LogPanel {{
        background-color: {p.bg_input};
        color: {p.text_secondary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
        padding: 8px;
        font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", monospace;
        font-size: 12px;
    }}

    /* --- Scrollbars --- */
    QScrollBar:vertical {{
        background: {p.bg_window};
        width: 10px;
        margin: 2px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border_strong};
        min-height: 24px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p.text_muted};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* --- Status Bar --- */
    QStatusBar {{
        background-color: {p.bg_elevated};
        color: {p.text_secondary};
        border-top: 1px solid {p.border_subtle};
        font-size: 12px;
    }}
    """


class ThemeManager(QObject):
    """Manages light/dark/system theme state and dynamic QSS application."""

    theme_changed = Signal(str)  # emits active palette name ('light' or 'dark')

    def __init__(self, app: QApplication, settings: AppSettings) -> None:
        super().__init__(app)
        self._app = app
        self._settings = settings

        # Listen for OS color scheme changes in Qt 6.5+
        style_hints = QGuiApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    def resolve_effective_mode(self) -> str:
        """Determine whether 'light' or 'dark' should be rendered."""
        pref = self._settings.theme_mode
        if pref in ("light", "dark"):
            return pref

        # Detect system theme via Qt6 styleHints or palette luminance
        style_hints = QGuiApplication.styleHints()
        if hasattr(style_hints, "colorScheme"):
            scheme = style_hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
            if scheme == Qt.ColorScheme.Light:
                return "light"

        window_color = QGuiApplication.palette().color(QPalette.ColorRole.Window)
        return "dark" if window_color.lightness() < 128 else "light"

    def current_palette(self) -> ThemePalette:
        """Return the active ThemePalette instance."""
        return (
            DARK_PALETTE
            if self.resolve_effective_mode() == "dark"
            else LIGHT_PALETTE
        )

    def apply_current_theme(self) -> None:
        """Compile and apply the QSS stylesheet for the active theme."""
        palette = self.current_palette()
        self._app.setStyleSheet(build_stylesheet(palette))
        self.theme_changed.emit(palette.name)

    def toggle_light_dark(self) -> str:
        """Toggle manually between Light and Dark themes and persist choice."""
        current = self.resolve_effective_mode()
        new_mode = "dark" if current == "light" else "light"
        self._settings.theme_mode = new_mode
        self._settings.sync()
        self.apply_current_theme()
        return new_mode

    def set_theme_mode(self, mode: str) -> None:
        """Set theme mode ('system', 'light', 'dark') and refresh UI."""
        self._settings.theme_mode = mode
        self._settings.sync()
        self.apply_current_theme()

    def _on_system_scheme_changed(self) -> None:
        if self._settings.theme_mode == "system":
            self.apply_current_theme()


def create_app_icon() -> QIcon:
    """Draw a classic-modern burgundy emblem icon for window and system tray."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Rounded badge background in deep burgundy
    painter.setPen(QPen(QColor("#D6CBB9"), 2.0))
    painter.setBrush(QColor("#7A202E"))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 14, 14)

    # Inner classic ring
    painter.setPen(QPen(QColor("#F5F2E9"), 1.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(9, 9, 46, 46), 10, 10)

    # Downward archival arrow + base tray
    pen = QPen(QColor("#FAF8F5"), 3.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    painter.drawLine(QPointF(32, 16), QPointF(32, 38))
    painter.drawLine(QPointF(23, 30), QPointF(32, 39))
    painter.drawLine(QPointF(41, 30), QPointF(32, 39))
    painter.drawLine(QPointF(20, 46), QPointF(44, 46))

    painter.end()
    return QIcon(pixmap)


def create_icon(name: str, is_dark: bool = False) -> QIcon:
    """Create crisp vector icons for buttons and toolbars using QPainter."""
    size = 20
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    stroke_color = QColor("#EAE6DF") if is_dark else QColor("#1E201D")
    accent_color = QColor("#B5374B") if is_dark else QColor("#7A202E")

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    pen = QPen(stroke_color, 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    if name == "paste":
        painter.drawRoundedRect(QRectF(4, 5, 12, 12), 2, 2)
        painter.setPen(QPen(accent_color, 1.8))
        painter.drawRoundedRect(QRectF(7, 2.5, 6, 3), 1, 1)
    elif name == "fetch":
        painter.drawEllipse(QRectF(3, 3, 10, 10))
        painter.setPen(QPen(accent_color, 2.0))
        painter.drawLine(QPointF(11.5, 11.5), QPointF(16.5, 16.5))
    elif name == "download":
        painter.setPen(QPen(QColor("#FAF8F5"), 2.0))
        painter.drawLine(QPointF(10, 3), QPointF(10, 13))
        painter.drawLine(QPointF(6, 9.5), QPointF(10, 13.5))
        painter.drawLine(QPointF(14, 9.5), QPointF(10, 13.5))
        painter.drawLine(QPointF(4, 16.5), QPointF(16, 16.5))
    elif name == "play":
        path = QPainterPath()
        path.moveTo(6, 4)
        path.lineTo(15, 10)
        path.lineTo(6, 16)
        path.closeSubpath()
        painter.setBrush(accent_color)
        painter.setPen(QPen(accent_color, 1.4))
        painter.drawPath(path)
    elif name == "pause":
        painter.drawLine(QPointF(7, 4.5), QPointF(7, 15.5))
        painter.drawLine(QPointF(13, 4.5), QPointF(13, 15.5))
    elif name == "cancel":
        painter.setPen(QPen(accent_color, 1.9))
        painter.drawLine(QPointF(5, 5), QPointF(15, 15))
        painter.drawLine(QPointF(15, 5), QPointF(5, 15))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(3, 6)
        path.lineTo(8, 6)
        path.lineTo(10, 8)
        path.lineTo(17, 8)
        path.lineTo(17, 15.5)
        path.lineTo(3, 15.5)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "clear":
        painter.drawLine(QPointF(4, 6), QPointF(16, 6))
        painter.drawRoundedRect(QRectF(6, 6, 8, 10.5), 1.5, 1.5)
        painter.drawLine(QPointF(8, 3.8), QPointF(12, 3.8))
    elif name == "settings":
        painter.drawEllipse(QRectF(6, 6, 8, 8))
        for pt1, pt2 in (
            ((10, 2), (10, 4.5)),
            ((10, 15.5), (10, 18)),
            ((2, 10), (4.5, 10)),
            ((15.5, 10), (18, 10)),
        ):
            painter.drawLine(QPointF(*pt1), QPointF(*pt2))
    elif name == "theme":
        painter.setPen(QPen(accent_color, 1.8))
        painter.drawEllipse(QRectF(4, 4, 12, 12))
        painter.setBrush(accent_color)
        painter.drawPie(QRectF(4, 4, 12, 12), 90 * 16, 180 * 16)
    elif name == "log":
        painter.drawRoundedRect(QRectF(3, 4, 14, 12), 2, 2)
        painter.drawLine(QPointF(6, 8), QPointF(9, 10))
        painter.drawLine(QPointF(6, 12), QPointF(9, 10))
        painter.drawLine(QPointF(11, 12), QPointF(14, 12))

    painter.end()
    return QIcon(pixmap)