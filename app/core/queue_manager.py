"""Queue scheduler managing concurrent yt-dlp worker lifecycles."""

from __future__ import annotations

from pathlib import Path
import uuid

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from app.core.downloader import (
    DownloadOptions,
    DownloadStatus,
    DownloadWorker,
    QueueItem,
)


class QueueManager(QObject):
    """Coordinates queued download items, concurrency limits, and worker signals."""

    item_added = Signal(object)  # QueueItem
    item_updated = Signal(object)  # QueueItem
    item_removed = Signal(str)  # item_id
    item_completed = Signal(object)  # QueueItem
    log_message = Signal(str)

    def __init__(self, max_concurrent: int = 2, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: dict[str, QueueItem] = {}
        self._order: list[str] = []
        self._active_workers: dict[str, DownloadWorker] = {}
        self._max_concurrent = max(1, min(5, max_concurrent))

        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(8)

    @property
    def max_concurrent(self) -> int:
        """Return the configured concurrency limit."""
        return self._max_concurrent

    def set_max_concurrent(self, limit: int) -> None:
        """Update the maximum number of simultaneous downloads and schedule pending tasks."""
        self._max_concurrent = max(1, min(5, int(limit)))
        self._schedule_next()

    def get_item(self, item_id: str) -> QueueItem | None:
        """Return a QueueItem by its identifier."""
        return self._items.get(item_id)

    def get_all_items(self) -> list[QueueItem]:
        """Return all queue items in insertion order."""
        return [self._items[iid] for iid in self._order if iid in self._items]

    def add_item(
        self,
        url: str,
        title: str,
        options: DownloadOptions,
        auto_start: bool = True,
    ) -> QueueItem:
        """Create a new QueueItem, register it, and schedule execution."""
        item_id = uuid.uuid4().hex[:10]
        output_dir = str(Path(options.download_dir).expanduser().resolve())
        item = QueueItem(
            item_id=item_id,
            url=url.strip(),
            title=title.strip() or url.strip(),
            options=options,
            status=DownloadStatus.QUEUED if auto_start else DownloadStatus.PAUSED,
            output_dir=output_dir,
        )
        self._items[item_id] = item
        self._order.append(item_id)
        self.item_added.emit(item)
        if auto_start:
            self._schedule_next()
        return item

    def start_or_resume_item(self, item_id: str) -> None:
        """Start or resume a paused/failed/canceled item."""
        item = self._items.get(item_id)
        if not item or item_id in self._active_workers:
            return

        if item.status in (
            DownloadStatus.PAUSED,
            DownloadStatus.FAILED,
            DownloadStatus.CANCELED,
            DownloadStatus.QUEUED,
        ):
            item.status = DownloadStatus.QUEUED
            item.error_message = ""
            self.item_updated.emit(item)
            self._schedule_next()

    def pause_item(self, item_id: str) -> None:
        """Pause an active or queued download item."""
        item = self._items.get(item_id)
        if not item:
            return

        worker = self._active_workers.get(item_id)
        if worker:
            worker.request_pause()
            item.speed_str = "—"
            item.eta_str = "—"
            self.item_updated.emit(item)
        elif item.status == DownloadStatus.QUEUED:
            item.status = DownloadStatus.PAUSED
            item.speed_str = "—"
            item.eta_str = "—"
            self.item_updated.emit(item)

    def cancel_item(self, item_id: str) -> None:
        """Cancel a queued, paused, or active download item."""
        item = self._items.get(item_id)
        if not item:
            return

        worker = self._active_workers.get(item_id)
        if worker:
            worker.request_cancel()
        else:
            item.status = DownloadStatus.CANCELED
            item.speed_str = "—"
            item.eta_str = "—"
            self.item_updated.emit(item)

    def clear_finished(self) -> int:
        """Remove all Completed and Canceled items from the queue."""
        removable = [
            iid
            for iid in self._order
            if iid in self._items
            and iid not in self._active_workers
            and self._items[iid].status
            in (DownloadStatus.COMPLETED, DownloadStatus.CANCELED)
        ]
        for iid in removable:
            self._items.pop(iid, None)
            self._order.remove(iid)
            self.item_removed.emit(iid)
        return len(removable)

    def shutdown(self) -> None:
        """Cancel all active workers gracefully when the application exits."""
        for worker in list(self._active_workers.values()):
            worker.request_cancel()
        self._thread_pool.waitForDone(2500)

    def _schedule_next(self) -> None:
        """Spawn workers for queued items up to the concurrency limit."""
        while len(self._active_workers) < self._max_concurrent:
            next_item: QueueItem | None = None
            for iid in self._order:
                candidate = self._items.get(iid)
                if (
                    candidate
                    and candidate.status == DownloadStatus.QUEUED
                    and iid not in self._active_workers
                ):
                    next_item = candidate
                    break

            if next_item is None:
                break

            worker = DownloadWorker(next_item)
            worker.signals.progress.connect(self._on_worker_progress)
            worker.signals.status_changed.connect(self._on_worker_status_changed)
            worker.signals.log.connect(self.log_message.emit)

            self._active_workers[next_item.item_id] = worker
            next_item.status = DownloadStatus.DOWNLOADING
            self.item_updated.emit(next_item)
            self._thread_pool.start(worker)

    @Slot(str, float, str, str, str)
    def _on_worker_progress(
        self,
        item_id: str,
        pct: float,
        speed_str: str,
        eta_str: str,
        size_str: str,
    ) -> None:
        """Update item metrics when a worker emits a progress hook update."""
        item = self._items.get(item_id)
        if not item:
            return
        item.progress = pct
        item.speed_str = speed_str
        item.eta_str = eta_str
        if size_str and size_str != "—":
            item.size_str = size_str
        self.item_updated.emit(item)

    @Slot(str, str, str)
    def _on_worker_status_changed(
        self,
        item_id: str,
        status_value: str,
        detail: str,
    ) -> None:
        """Handle worker state transitions and launch subsequent queued items."""
        item = self._items.get(item_id)
        if not item:
            self._active_workers.pop(item_id, None)
            self._schedule_next()
            return

        new_status = DownloadStatus(status_value)
        item.status = new_status

        if new_status == DownloadStatus.PROCESSING:
            item.speed_str = "Merging..."
            item.eta_str = "—"
            self.item_updated.emit(item)
            return

        if new_status in (
            DownloadStatus.COMPLETED,
            DownloadStatus.PAUSED,
            DownloadStatus.FAILED,
            DownloadStatus.CANCELED,
        ):
            self._active_workers.pop(item_id, None)
            item.speed_str = "—"
            item.eta_str = "—"

            if new_status == DownloadStatus.COMPLETED:
                item.progress = 100.0
                if detail:
                    item.output_filepath = detail
                self.item_updated.emit(item)
                self.item_completed.emit(item)
            elif new_status == DownloadStatus.FAILED:
                item.error_message = detail
                self.item_updated.emit(item)
            else:
                self.item_updated.emit(item)

            self._schedule_next()
        else:
            self.item_updated.emit(item)