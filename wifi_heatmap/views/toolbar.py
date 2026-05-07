from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ToolbarWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: #2a2a3a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignTop)

        header = QLabel("Werkzeuge")
        header.setStyleSheet("color: #4fc3f7; font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        placeholder = QLabel("(Platzhalter)")
        placeholder.setStyleSheet("color: #606070; font-size: 11px;")
        layout.addWidget(placeholder)

        layout.addStretch()
