"""Sender List dialog — browse all unique senders and block/delete from them."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mailsweep.utils.size_fmt import human_size


class SenderListDialog(QDialog):
    """Shows all unique senders with message count and total size.

    Emits:
        delete_requested(emails)         — delete all messages from senders
        block_delete_requested(emails)   — add to blocklist + delete all
    """

    delete_requested = pyqtSignal(list)             # list[str]
    block_delete_requested = pyqtSignal(list)       # list[str]
    backup_delete_requested = pyqtSignal(list)      # list[str]

    def __init__(self, rows: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("All Senders")
        self.resize(700, 500)
        self._all_rows = rows

        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name or email…")
        self._search.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self._search)
        layout.addLayout(search_layout)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Name", "Email", "Messages", "Size"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 200)
        self._table.setColumnWidth(1, 220)
        self._table.setColumnWidth(2, 80)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        # Status label
        self._count_label = QLabel()
        self._count_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._count_label)

        # Close button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._populate(rows)

    def _populate(self, rows: list[dict]) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            full_from = row.get("from_addr", "") or ""
            email = row.get("sender_email", "") or ""
            if "<" in full_from:
                name = full_from[:full_from.index("<")].strip().strip('"')
            else:
                name = email

            count = row.get("message_count", 0)
            size = row.get("total_size_bytes", 0)

            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, email)
            email_item = QTableWidgetItem(email)

            count_item = QTableWidgetItem()
            count_item.setData(Qt.ItemDataRole.DisplayRole, count)

            size_item = QTableWidgetItem(human_size(size))
            size_item.setData(Qt.ItemDataRole.UserRole, size)

            self._table.setItem(i, 0, name_item)
            self._table.setItem(i, 1, email_item)
            self._table.setItem(i, 2, count_item)
            self._table.setItem(i, 3, size_item)

        self._table.setSortingEnabled(True)
        self._table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self._update_status(len(rows))

    def _apply_filter(self, text: str) -> None:
        text = text.strip().lower()
        filtered = [
            r for r in self._all_rows
            if text in (r.get("sender_email") or "").lower()
            or text in (r.get("from_addr") or "").lower()
        ]
        self._populate(filtered)

    def _selected_emails(self) -> list[str]:
        seen: set[int] = set()
        emails: list[str] = []
        for idx in self._table.selectedIndexes():
            row = idx.row()
            if row in seen:
                continue
            seen.add(row)
            item = self._table.item(row, 0)
            if item:
                email = item.data(Qt.ItemDataRole.UserRole)
                if email:
                    emails.append(email)
        return emails

    def _on_selection_changed(self) -> None:
        emails = self._selected_emails()
        n = len(emails)
        total = self._table.rowCount()
        if n:
            self._count_label.setText(f"{n} of {total:,} sender(s) selected")
        else:
            self._update_status(total)

    def _update_status(self, total: int) -> None:
        self._count_label.setText(f"{total:,} sender(s)")

    def _on_context_menu(self, pos) -> None:
        emails = self._selected_emails()
        if not emails:
            return
        n = len(emails)
        label = f"{n} sender(s)" if n > 1 else emails[0]
        menu = QMenu(self)
        menu.addAction(f"Delete All From {label}", lambda: self.delete_requested.emit(emails))
        menu.addAction(f"Block && Delete All From {label}", lambda: self.block_delete_requested.emit(emails))
        menu.addAction(f"Backup && Delete All From {label}", lambda: self.backup_delete_requested.emit(emails))
        menu.exec(self._table.viewport().mapToGlobal(pos))
