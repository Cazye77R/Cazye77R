from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from views.canvas import CanvasMode

_TOOL_BTN = """
QPushButton {
    background-color: #353545;
    color: #d0d0e0;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    padding: 5px 6px;
    text-align: left;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #404058;
    border-color: #5a5a7a;
}
QPushButton:checked {
    background-color: #1a4060;
    border: 2px solid #4fc3f7;
    color: #4fc3f7;
    font-weight: bold;
}
QPushButton:pressed { background-color: #1a3050; }
"""

_MEASURE_DISABLED = """
QPushButton {
    background-color: #252535;
    color: #3a5a6a;
    border: 1px solid #2a3a4a;
    border-radius: 4px;
    padding: 7px 4px;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
}
"""

_MEASURE_ENABLED = """
QPushButton {
    background-color: #0a4060;
    color: #4fc3f7;
    border: 2px solid #4fc3f7;
    border-radius: 4px;
    padding: 7px 4px;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
}
QPushButton:hover { background-color: #0a5070; }
QPushButton:pressed { background-color: #083040; }
"""

_MEASURE_RUNNING = """
QPushButton {
    background-color: #0a2a3a;
    color: #6090a0;
    border: 2px solid #1a5070;
    border-radius: 4px;
    padding: 7px 4px;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 0px;
}
"""

_SPIN_FRAMES = ["◐", "◓", "◑", "◒"]

_CB_STYLE = "QCheckBox { color: #b0b0c8; font-size: 11px; } QCheckBox::indicator { width: 13px; height: 13px; }"

_SLIDER_STYLE = (
    "QSlider::groove:horizontal { background:#3a3a4a; height:4px; border-radius:2px; }"
    "QSlider::sub-page:horizontal { background:#4fc3f7; height:4px; border-radius:2px; }"
    "QSlider::handle:horizontal { background:#4fc3f7; width:12px; height:12px;"
    "  margin:-4px 0; border-radius:6px; }"
)

_TOOLS: list[tuple[str, CanvasMode]] = [
    ("↖  Auswählen", CanvasMode.SELECT),
    ("▭  Rechteck",  CanvasMode.RECT),
    ("╱  Linie",     CanvasMode.LINE),
    ("📡  Router",    CanvasMode.ROUTER),
    ("📍  Messpunkt", CanvasMode.MEASURE),
    ("🗑  Löschen",   CanvasMode.DELETE),
]


def _hr() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #3a3a4a; margin: 3px 0;")
    return f


class ToolbarWidget(QWidget):
    mode_changed      = Signal(CanvasMode)
    measure_triggered = Signal()
    snap_points_changed = Signal(bool)
    grid_snap_changed   = Signal(bool)
    grid_size_changed   = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: #2a2a3a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 8, 7, 8)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Tool buttons ───────────────────────────────────────
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._mode_btns: dict[CanvasMode, QPushButton] = {}

        for label, mode in _TOOLS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setStyleSheet(_TOOL_BTN)
            btn.clicked.connect(lambda _checked, m=mode: self._on_tool(m))
            self._btn_group.addButton(btn)
            self._mode_btns[mode] = btn
            layout.addWidget(btn)

        self._mode_btns[CanvasMode.SELECT].setChecked(True)

        layout.addWidget(_hr())

        # ── MESSEN button ──────────────────────────────────────
        self._measure_btn = QPushButton("📶  MESSEN")
        self._measure_btn.setFixedHeight(38)
        self._measure_btn.setEnabled(False)
        self._measure_btn.setStyleSheet(_MEASURE_DISABLED)
        self._measure_btn.clicked.connect(self.measure_triggered)
        layout.addWidget(self._measure_btn)

        self._spin_idx   = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._on_spin_tick)

        layout.addWidget(_hr())

        # ── Snap checkboxes ────────────────────────────────────
        self._snap_pts_cb = QCheckBox("Snap an Punkte")
        self._snap_pts_cb.setChecked(True)
        self._snap_pts_cb.setStyleSheet(_CB_STYLE)
        self._snap_pts_cb.toggled.connect(self.snap_points_changed)
        layout.addWidget(self._snap_pts_cb)

        self._grid_snap_cb = QCheckBox("Raster-Snap")
        self._grid_snap_cb.setChecked(False)
        self._grid_snap_cb.setStyleSheet(_CB_STYLE)
        self._grid_snap_cb.toggled.connect(self.grid_snap_changed)
        layout.addWidget(self._grid_snap_cb)

        # ── Grid size slider ───────────────────────────────────
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        lbl = QLabel("Raster:")
        lbl.setStyleSheet("color: #b0b0c8; font-size: 11px;")
        self._grid_val_lbl = QLabel("20 px")
        self._grid_val_lbl.setStyleSheet("color: #4fc3f7; font-size: 11px;")
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(self._grid_val_lbl)
        layout.addLayout(row)

        self._grid_slider = QSlider(Qt.Orientation.Horizontal)
        self._grid_slider.setRange(10, 100)
        self._grid_slider.setValue(20)
        self._grid_slider.setStyleSheet(_SLIDER_STYLE)
        self._grid_slider.valueChanged.connect(self._on_grid_size)
        layout.addWidget(self._grid_slider)

        layout.addStretch()

    # ── Public API ─────────────────────────────────────────────

    def set_active_mode(self, mode: CanvasMode) -> None:
        btn = self._mode_btns.get(mode)
        if btn:
            btn.setChecked(True)

    def set_measure_enabled(self, enabled: bool) -> None:
        self._spin_timer.stop()
        self._measure_btn.setText("📶  MESSEN")
        self._measure_btn.setEnabled(enabled)
        self._measure_btn.setStyleSheet(
            _MEASURE_ENABLED if enabled else _MEASURE_DISABLED
        )

    def set_measure_running(self, running: bool) -> None:
        """Switch button appearance between 'ready' and 'scan in progress'."""
        if running:
            self._spin_idx = 0
            self._spin_timer.start(160)
            self._measure_btn.setEnabled(False)
            self._measure_btn.setStyleSheet(_MEASURE_RUNNING)
        else:
            self._spin_timer.stop()
            self._measure_btn.setText("📶  MESSEN")

    def _on_spin_tick(self) -> None:
        frame = _SPIN_FRAMES[self._spin_idx % len(_SPIN_FRAMES)]
        self._measure_btn.setText(f"{frame}  Messung läuft…")
        self._spin_idx += 1

    # ── Slots ──────────────────────────────────────────────────

    def _on_tool(self, mode: CanvasMode) -> None:
        self.mode_changed.emit(mode)

    def _on_grid_size(self, value: int) -> None:
        self._grid_val_lbl.setText(f"{value} px")
        self.grid_size_changed.emit(value)
