"""Queue table widget displaying per-item progress bars and lifecycle actions."""

from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.core.downloader import DownloadStatus, QueueItem
from app.ui.theme import create_icon


@dataclass
class _RowControls:
    """Widget references stored for a single row in the QueueTableWidget."""

    progress_bar: QProgressBar
    action_container: QWidget
    btn_start_resume: QPushButton
    btn_pause: QPushButton
    btn_cancel: QPushButton
    btn_open_folder: QPushButton


class QueueTableWidget(QTableWidget):
    """Table displaying queued downloads with progress bars and action controls."""

    start_resume_requested = Signal(str)  # item_id
    pause_requested = Signal(str)         # item_id
    cancel_requested = Signal(str)        # item_id
    open_folder_requested = Signal(str)   # item_id

    COL_TITLE = 0
    COL_STATUS = 1
    COL_PROGRESS = 2
    COL_SPEED = 3
    COL_ETA = 4
    COL_SIZE = 5
    COL_ACTIONS = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 7, parent)
        self._row_ids: list[str] = []
        self._controls: dict[str, _RowControls] = {}
        self._is_dark: bool = False

        self._setup_table()

    def _setup_table(self) -> None:
        """Configure headers, column stretching, and table behaviors."""
        self.setHorizontalHeaderLabels(
            ["Title", "Status", "Progress", "Speed", "ETA", "Size", "Actions"]
        )
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(42)

        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PROGRESS, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_PROGRESS, 155)
        header.setSectionResizeMode(self.COL_SPEED, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_SPEED, 95)
        header.setSectionResizeMode(self.COL_ETA, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_ETA, 75)
        header.setSectionResizeMode(self.COL_SIZE, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_SIZE, 90)
        header.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_ACTIONS, 195)

    def refresh_icons(self, is_dark: bool) -> None:
        """Update row button icons when the user switches between light and dark theme."""
        self._is_dark = is_dark
        for ctrl in self._controls.values():
            ctrl.btn_start_resume.setIcon(create_icon("play", is_dark))
            ctrl.btn_pause.setIcon(create_icon("pause", is_dark))
            ctrl.btn_cancel.setIcon(create_icon("cancel", is_dark))
            ctrl.btn_open_folder.setIcon(create_icon("folder", is_dark))

    def add_queue_item(self, item: QueueItem) -> None:
        """Insert a new QueueItem row at the bottom of the table."""
        row = self.rowCount()
        self.insertRow(row)
        self._row_ids.append(item.item_id)

        title_cell = QTableWidgetItem(item.title)
        title_cell.setToolTip(f"{item.title}\nURL: {item.url}")
        self.setItem(row, self.COL_TITLE, title_cell)

        status_cell = QTableWidgetItem(item.status.value)
        status_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_STATUS, status_cell)

        progress_bar = QProgressBar(self)
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(item.progress))
        progress_bar.setFormat("%p%")

        progress_wrapper = QWidget(self)
        p_layout = QHBoxLayout(progress_wrapper)
        p_layout.setContentsMargins(6, 6, 6, 6)
        p_layout.addWidget(progress_bar)
        self.setCellWidget(row, self.COL_PROGRESS, progress_wrapper)

        speed_cell = QTableWidgetItem(item.speed_str)
        speed_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, self.COL_SPEED, speed_cell)

        eta_cell = QTableWidgetItem(item.eta_str)
        eta_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_ETA, eta_cell)

        size_cell = QTableWidgetItem(item.size_str)
        size_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, self.COL_SIZE, size_cell)

        # Build action buttons
        action_container = QWidget(self)
        a_layout = QHBoxLayout(action_container)
        a_layout.setContentsMargins(4, 3, 4, 3)
        a_layout.setSpacing(4)

        btn_start_resume = QPushButton("Resume", action_container)
        btn_start_resume.setObjectName("TableActionButton")
        btn_start_resume.setIcon(create_icon("play", self._is_dark))
        btn_start_resume.setToolTip("Start or resume download")
        btn_start_resume.clicked.connect(
            lambda _checked=False, iid=item.item_id: self.start_resume_requested.emit(iid)
        )

        btn_pause = QPushButton("Pause", action_container)
        btn_pause.setObjectName("TableActionButton")
        btn_pause.setIcon(create_icon("pause", self._is_dark))
        btn_pause.setToolTip("Pause active download")
        btn_pause.clicked.connect(
            lambda _checked=False, iid=item.item_id: self.pause_requested.emit(iid)
        )

        btn_cancel = QPushButton("", action_container)
        btn_cancel.setObjectName("TableActionButton")
        btn_cancel.setIcon(create_icon("cancel", self._is_dark))
        btn_cancel.setToolTip("Cancel download")
        btn_cancel.clicked.connect(
            lambda _checked=False, iid=item.item_id: self.cancel_requested.emit(iid)
        )

        btn_open_folder = QPushButton("Folder", action_container)
        btn_open_folder.setObjectName("TableActionButton")
        btn_open_folder.setIcon(create_icon("folder", self._is_dark))
        btn_open_folder.setToolTip("Open destination folder")
        btn_open_folder.clicked.connect(
            lambda _checked=False, iid=item.item_id: self.open_folder_requested.emit(iid)
        )

        a_layout.addWidget(btn_start_resume)
        a_layout.addWidget(btn_pause)
        a_layout.addWidget(btn_open_folder)
        a_layout.addWidget(btn_cancel)
        self.setCellWidget(row, self.COL_ACTIONS, action_container)

        self._controls[item.item_id] = _RowControls(
            progress_bar=progress_bar,
            action_container=action_container,
            btn_start_resume=btn_start_resume,
            btn_pause=btn_pause,
            btn_cancel=btn_cancel,
            btn_open_folder=btn_open_folder,
        )
        self.update_queue_item(item)

    def update_queue_item(self, item: QueueItem) -> None:
        """Refresh cells and button states for an existing QueueItem."""
        if item.item_id not in self._row_ids:
            return
        row = self._row_ids.index(item.item_id)

        title_cell = self.item(row, self.COL_TITLE)
        if title_cell:
            title_cell.setText(item.title)
            tooltip = f"{item.title}\nURL: {item.url}"
            if item.error_message:
                tooltip += f"\nError: {item.error_message}"
            title_cell.setToolTip(tooltip)

        status_cell = self.item(row, self.COL_STATUS)
        if status_cell:
            status_cell.setText(item.status.value)
            if item.error_message:
                status_cell.setToolTip(item.error_message)
            else:
                status_cell.setToolTip("")

        speed_cell = self.item(row, self.COL_SPEED)
        if speed_cell:
            speed_cell.setText(item.speed_str)

        eta_cell = self.item(row, self.COL_ETA)
        if eta_cell:
            eta_cell.setText(item.eta_str)

        size_cell = self.item(row, self.COL_SIZE)
        if size_cell:
            size_cell.setText(item.size_str)

        ctrl = self._controls.get(item.item_id)
        if not ctrl:
            return

        ctrl.progress_bar.setValue(int(round(item.progress)))

        st = item.status
        is_active = st in (DownloadStatus.DOWNLOADING, DownloadStatus.PROCESSING)
        is_resumable = st in (
            DownloadStatus.PAUSED,
            DownloadStatus.FAILED,
            DownloadStatus.CANCELED,
        )
        is_completed = st == DownloadStatus.COMPLETED

        ctrl.btn_start_resume.setVisible(is_resumable)
        ctrl.btn_start_resume.setText("Retry" if st == DownloadStatus.FAILED else "Resume")

        ctrl.btn_pause.setVisible(is_active or st == DownloadStatus.QUEUED)
        ctrl.btn_pause.setEnabled(st != DownloadStatus.PROCESSING)

        ctrl.btn_cancel.setVisible(not is_completed and st != DownloadStatus.CANCELED)
        ctrl.btn_open_folder.setVisible(is_completed)

    def remove_queue_item(self, item_id: str) -> None:
        """Delete a row corresponding to item_id from the table."""
        if item_id not in self._row_ids:
            return
        row = self._row_ids.index(item_id)
        self.removeRow(row)
        self._row_ids.remove(item_id)
        self._controls.pop(item_id, None)