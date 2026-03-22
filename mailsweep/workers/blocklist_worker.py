"""BlocklistSyncWorker — fetches the community blocklist from a URL."""
from __future__ import annotations
import urllib.request
from PyQt6.QtCore import QObject, pyqtSignal


class BlocklistSyncWorker(QObject):
    finished = pyqtSignal(int, str)  # added_count, error_msg (empty = success)

    def __init__(self, blocklist_repo, url: str, parent=None):
        super().__init__(parent)
        self._repo = blocklist_repo
        self._url = url

    def run(self) -> None:
        try:
            with urllib.request.urlopen(self._url, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            self.finished.emit(0, f"Failed to fetch blocklist: {exc}")
            return

        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        self._repo.clear_github()
        added = self._repo.add_many(lines, source="github")
        self.finished.emit(added, "")
