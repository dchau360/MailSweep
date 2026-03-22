"""Blocklist Manager dialog."""
from __future__ import annotations
from pathlib import Path

import mailsweep.config as cfg
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from mailsweep.workers.blocklist_worker import BlocklistSyncWorker


class BlocklistDialog(QDialog):
    def __init__(self, blocklist_repo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = blocklist_repo
        self.setWindowTitle("Blocklist Manager")
        self.resize(520, 520)
        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Blocked senders are flagged during scan.\n"
            "Entries marked <b>github</b> come from the community list."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Pattern", "Source", "Added"])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setColumnWidth(0, 240)
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 140)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table, stretch=1)

        # Add entry row
        add_row = QHBoxLayout()
        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("email@example.com  or  @domain.com")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_add)
        self._add_input.returnPressed.connect(self._on_add)
        add_row.addWidget(self._add_input, stretch=1)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # Action buttons
        btn_row = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove)
        export_btn = QPushButton("Export to File…")
        export_btn.clicked.connect(self._on_export)
        self._sync_btn = QPushButton("Sync from Community URL")
        self._sync_btn.clicked.connect(self._on_sync_github)
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(self._sync_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

    def _refresh_table(self) -> None:
        entries = self._repo.get_all()
        self._table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            self._table.setItem(i, 0, QTableWidgetItem(e["pattern"]))
            self._table.setItem(i, 1, QTableWidgetItem(e["source"]))
            self._table.setItem(i, 2, QTableWidgetItem(e["added_at"][:16]))

    def _on_add(self) -> None:
        pattern = self._add_input.text().strip().lower()
        if not pattern:
            return
        self._repo.add(pattern, source="local")
        self._add_input.clear()
        self._refresh_table()

    def _on_double_click(self, item: QTableWidgetItem) -> None:
        """Allow editing the pattern of a local entry by double-clicking."""
        row = item.row()
        source_item = self._table.item(row, 1)
        if source_item and source_item.text() != "local":
            QMessageBox.information(self, "Read Only", "Community entries cannot be edited here.\nSync again to refresh them.")
            return
        pattern_item = self._table.item(row, 0)
        if not pattern_item:
            return
        old_pattern = pattern_item.text()
        self._add_input.setText(old_pattern)
        self._repo.remove(old_pattern)
        self._refresh_table()
        self._add_input.setFocus()

    def _on_remove(self) -> None:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        for row in rows:
            pattern = self._table.item(row, 0).text()
            self._repo.remove(pattern)
        self._refresh_table()

    def _on_export(self) -> None:
        """Export local blocklist entries to a text file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Blocklist",
            str(Path.home() / "blocklist.txt"),
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return
        entries = self._repo.get_all()
        local = [e for e in entries if e["source"] == "local"]
        lines = [
            "# MailSweep Blocklist",
            "# Format: exact email (spam@example.com) or whole domain (@example.com)",
            "# Lines starting with # are comments.",
            "",
        ]
        lines += [e["pattern"] for e in local]
        try:
            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(local)} local entries to:\n{path}",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _on_sync_github(self) -> None:
        url = cfg.BLOCKLIST_COMMUNITY_URL.strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Set a community blocklist URL in Settings first.")
            return
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Syncing…")
        self._thread = QThread()
        self._worker = BlocklistSyncWorker(self._repo, url)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_sync_done(self, added: int, error: str) -> None:
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("Sync from Community URL")
        if error:
            QMessageBox.warning(self, "Sync Failed", error)
        else:
            QMessageBox.information(
                self, "Sync Complete",
                f"Added {added} new entries from community blocklist.",
            )
        self._refresh_table()
