from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class PathSelection:
    paths: list[Path]

    def as_strings(self) -> list[str]:
        return [str(p) for p in self.paths]


class PathListWidget(QListWidget):
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                p = url.toLocalFile()
                if p:
                    paths.append(Path(p))
            self.add_paths(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def add_paths(self, paths: Iterable[Path]) -> None:
        existing = set(self.get_paths())
        added = False
        for p in paths:
            p = Path(p)
            if p in existing:
                continue
            item = QListWidgetItem(str(p))
            self.addItem(item)
            existing.add(p)
            added = True
        if added:
            self.changed.emit()

    def remove_selected(self) -> None:
        for item in self.selectedItems():
            self.takeItem(self.row(item))
        self.changed.emit()

    def clear_all(self) -> None:
        self.clear()
        self.changed.emit()

    def get_paths(self) -> list[Path]:
        out = []
        for i in range(self.count()):
            out.append(Path(self.item(i).text()))
        return out


class LogBox(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)

    def log(self, text: str) -> None:
        self.appendPlainText(text)


class PathListPanel(QWidget):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = QLabel(title)
        self.list = PathListWidget(self)
        self.btn_add_files = QPushButton("Add files")
        self.btn_add_folder = QPushButton("Add folder")
        self.btn_remove = QPushButton("Remove selected")
        self.btn_clear = QPushButton("Clear")

        top = QHBoxLayout()
        top.addWidget(self.title)
        top.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_add_files)
        buttons.addWidget(self.btn_add_folder)
        buttons.addWidget(self.btn_remove)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.setLayout(layout)