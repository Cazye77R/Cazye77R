from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models.floor import Floor
from models.measurement import Measurement
from utils.colors import dbm_to_color

# ── Shared styles ─────────────────────────────────────────────────────────────

_HDR  = "color: #4fc3f7; font-weight: bold; font-size: 12px; padding-bottom: 2px;"
_LBL  = "color: #7080a0; font-size: 11px;"
_VAL  = "color: #e0e0e0; font-size: 12px;"
_MUTED = "color: #505060; font-size: 11px; font-style: italic;"

_SLIDER = (
    "QSlider::groove:horizontal { background:#3a3a4a; height:4px; border-radius:2px; }"
    "QSlider::sub-page:horizontal { background:#4fc3f7; height:4px; border-radius:2px; }"
    "QSlider::handle:horizontal { background:#4fc3f7; width:12px; height:12px;"
    "  margin:-4px 0; border-radius:6px; }"
)

_BTN = """
QPushButton {
    background-color: #2a2a3a; color: #e0e0e0;
    border: 1px solid #3a3a4a; padding: 4px 8px;
    border-radius: 3px; font-size: 11px;
}
QPushButton:hover { background-color: #4fc3f7; color: #1e1e2e; }
QPushButton:pressed { background-color: #0288d1; color: #fff; }
"""

_BTN_DANGER = """
QPushButton {
    background-color: #2a1515; color: #ff6060;
    border: 1px solid #4a2020; padding: 4px 8px;
    border-radius: 3px; font-size: 11px;
}
QPushButton:hover { background-color: #ff4040; color: #fff; }
"""


def _hr() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #3a3a4a; margin: 3px 0;")
    return f


def _label(text: str) -> QLabel:
    w = QLabel(text)
    w.setStyleSheet(_LBL)
    return w


def _value(text: str = "—") -> QLabel:
    w = QLabel(text)
    w.setStyleSheet(_VAL)
    w.setWordWrap(True)
    return w


# ── Signal strength bar ───────────────────────────────────────────────────────

class _SignalBar(QWidget):
    """Thin horizontal bar filled proportionally with the signal color."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(7)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._dbm = -100.0
        self._pct = 0

    def set_value(self, dbm: float, pct: int) -> None:
        self._dbm = dbm
        self._pct = pct
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#3a3a4a"))
        fill_w = max(0, int(w * self._pct / 100))
        if fill_w:
            p.fillRect(0, 0, fill_w, h, dbm_to_color(self._dbm))
        p.end()


# ── Floor info page ───────────────────────────────────────────────────────────

class _FloorPage(QWidget):
    opacity_changed    = Signal(int)          # 0–100
    thresholds_changed = Signal(float, float) # min_dbm, max_dbm
    calibrate_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        hdr = QLabel("Eigenschaften")
        hdr.setStyleSheet(_HDR)
        lay.addWidget(hdr)
        lay.addWidget(_hr())

        # Floor info
        self._floor_name  = _value()
        self._floor_count = _value()
        row_n = QHBoxLayout()
        row_n.addWidget(_label("Etage:"))
        row_n.addWidget(self._floor_name)
        lay.addLayout(row_n)
        row_c = QHBoxLayout()
        row_c.addWidget(_label("Messpunkte:"))
        row_c.addWidget(self._floor_count)
        lay.addLayout(row_c)

        lay.addWidget(_hr())

        # Heatmap opacity
        hdr2 = QLabel("Heatmap")
        hdr2.setStyleSheet(_HDR)
        lay.addWidget(hdr2)

        op_row = QHBoxLayout()
        op_row.addWidget(_label("Deckkraft:"))
        self._op_label = QLabel("50 %")
        self._op_label.setStyleSheet("color:#4fc3f7; font-size:11px;")
        op_row.addStretch()
        op_row.addWidget(self._op_label)
        lay.addLayout(op_row)

        self._op_slider = QSlider(Qt.Orientation.Horizontal)
        self._op_slider.setRange(0, 100)
        self._op_slider.setValue(50)
        self._op_slider.setStyleSheet(_SLIDER)
        self._op_slider.valueChanged.connect(self._on_opacity)
        lay.addWidget(self._op_slider)

        lay.addWidget(_hr())

        # Threshold sliders
        hdr3 = QLabel("Schwellenwerte")
        hdr3.setStyleSheet(_HDR)
        lay.addWidget(hdr3)

        min_row = QHBoxLayout()
        min_row.addWidget(_label("Schlecht (Min):"))
        self._min_lbl = QLabel("-90 dBm")
        self._min_lbl.setStyleSheet("color:#ff6060; font-size:11px;")
        min_row.addStretch()
        min_row.addWidget(self._min_lbl)
        lay.addLayout(min_row)
        self._min_slider = QSlider(Qt.Orientation.Horizontal)
        self._min_slider.setRange(-120, -30)
        self._min_slider.setValue(-90)
        self._min_slider.setStyleSheet(_SLIDER)
        self._min_slider.valueChanged.connect(self._on_threshold)
        lay.addWidget(self._min_slider)

        max_row = QHBoxLayout()
        max_row.addWidget(_label("Sehr gut (Max):"))
        self._max_lbl = QLabel("-30 dBm")
        self._max_lbl.setStyleSheet("color:#60ff80; font-size:11px;")
        max_row.addStretch()
        max_row.addWidget(self._max_lbl)
        lay.addLayout(max_row)
        self._max_slider = QSlider(Qt.Orientation.Horizontal)
        self._max_slider.setRange(-120, -30)
        self._max_slider.setValue(-30)
        self._max_slider.setStyleSheet(_SLIDER)
        self._max_slider.valueChanged.connect(self._on_threshold)
        lay.addWidget(self._max_slider)

        lay.addWidget(_hr())

        # Scale calibration
        hdr4 = QLabel("Maßstab")
        hdr4.setStyleSheet(_HDR)
        lay.addWidget(hdr4)

        self._scale_lbl = QLabel("nicht kalibriert")
        self._scale_lbl.setStyleSheet(_MUTED)
        lay.addWidget(self._scale_lbl)

        self._cal_btn = QPushButton("Kalibrieren")
        self._cal_btn.setStyleSheet(_BTN)
        self._cal_btn.clicked.connect(self.calibrate_requested)
        lay.addWidget(self._cal_btn)

        lay.addStretch()

    def update_floor(self, floor: Optional[Floor]) -> None:
        if floor is None:
            self._floor_name.setText("—")
            self._floor_count.setText("0")
        else:
            self._floor_name.setText(floor.name)
            self._floor_count.setText(str(len(floor.measurements)))

    def update_scale(self, ppm: Optional[float]) -> None:
        if ppm is None:
            self._scale_lbl.setText("nicht kalibriert")
            self._scale_lbl.setStyleSheet(_MUTED)
            self._cal_btn.setText("Kalibrieren")
        else:
            self._scale_lbl.setText(f"1 m = {ppm:.1f} px")
            self._scale_lbl.setStyleSheet("color:#60c060; font-size:11px;")
            self._cal_btn.setText("Neu kalibrieren")

    def _on_opacity(self, v: int) -> None:
        self._op_label.setText(f"{v} %")
        self.opacity_changed.emit(v)

    def _on_threshold(self, _: int) -> None:
        mn = float(self._min_slider.value())
        mx = float(self._max_slider.value())
        if mn >= mx:
            return
        self._min_lbl.setText(f"{mn:.0f} dBm")
        self._max_lbl.setText(f"{mx:.0f} dBm")
        self.thresholds_changed.emit(mn, mx)


# ── Measurement detail page ───────────────────────────────────────────────────

class _MeasurePage(QWidget):
    remeasure_requested = Signal(object)  # Measurement
    delete_requested    = Signal(object)  # Measurement

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        hdr = QLabel("Messpunkt")
        hdr.setStyleSheet(_HDR)
        lay.addWidget(hdr)
        lay.addWidget(_hr())

        # Signal bar + dBm row
        self._bar = _SignalBar()
        lay.addWidget(self._bar)

        dbm_row = QHBoxLayout()
        self._dbm_val = QLabel()
        self._dbm_val.setStyleSheet("color:#e0e0e0; font-size:14px; font-weight:bold;")
        self._pct_val = QLabel()
        self._pct_val.setStyleSheet("color:#9090b0; font-size:11px;")
        dbm_row.addWidget(self._dbm_val)
        dbm_row.addStretch()
        dbm_row.addWidget(self._pct_val)
        lay.addLayout(dbm_row)

        lay.addWidget(_hr())

        # Detail rows
        self._ssid_lbl    = _label("SSID:")
        self._ssid_val    = _value()
        self._band_lbl    = _label("Kanal / Band:")
        self._band_val    = _value()
        self._std_lbl     = _label("Std.Abweichung:")
        self._std_val     = _value()
        self._time_lbl    = _label("Zeitstempel:")
        self._time_val    = _value()
        self._bssid_lbl   = _label("BSSID:")
        self._bssid_val   = _value()

        for lbl, val in [
            (self._ssid_lbl,  self._ssid_val),
            (self._band_lbl,  self._band_val),
            (self._std_lbl,   self._std_val),
            (self._time_lbl,  self._time_val),
            (self._bssid_lbl, self._bssid_val),
        ]:
            row = QHBoxLayout()
            row.addWidget(lbl)
            row.addWidget(val, stretch=1)
            lay.addLayout(row)

        lay.addWidget(_hr())

        # Action buttons
        btn_row = QHBoxLayout()
        self._remeasure_btn = QPushButton("⟳  Neu messen")
        self._remeasure_btn.setStyleSheet(_BTN)
        self._delete_btn    = QPushButton("🗑  Löschen")
        self._delete_btn.setStyleSheet(_BTN_DANGER)
        btn_row.addWidget(self._remeasure_btn)
        btn_row.addWidget(self._delete_btn)
        lay.addLayout(btn_row)

        lay.addStretch()

        self._m: Optional[Measurement] = None
        self._remeasure_btn.clicked.connect(self._on_remeasure)
        self._delete_btn.clicked.connect(self._on_delete)

    def update_measurement(self, m: Measurement) -> None:
        self._m = m
        self._bar.set_value(m.dbm, m.signal_percent)
        self._dbm_val.setText(f"{m.dbm:.1f} dBm")
        self._pct_val.setText(f"({m.signal_percent} %)")
        self._ssid_val.setText(m.ssid or "—")
        self._band_val.setText(
            f"CH {m.channel}  ·  {m.band}" if m.channel else m.band or "—"
        )
        if m.std_deviation and m.std_deviation > 0:
            self._std_val.setText(f"± {m.std_deviation:.1f} dB")
        else:
            self._std_val.setText("—")
        self._time_val.setText(m.timestamp.strftime("%H:%M:%S  %d.%m.%Y"))
        self._bssid_val.setText(m.bssid or "—")

    def _on_remeasure(self) -> None:
        if self._m is not None:
            self.remeasure_requested.emit(self._m)

    def _on_delete(self) -> None:
        if self._m is not None:
            self.delete_requested.emit(self._m)


# ── Public panel ──────────────────────────────────────────────────────────────

class PropertiesPanel(QWidget):
    """
    Right-side panel that switches between two pages:
      • _FloorPage — shown when no measurement is selected
      • _MeasurePage — shown when a measurement dot is selected
    """

    remeasure_requested          = Signal(object)  # Measurement
    delete_measurement_requested = Signal(object)  # Measurement
    heatmap_opacity_changed      = Signal(int)     # 0–100
    thresholds_changed           = Signal(float, float)  # min_dbm, max_dbm
    calibrate_requested          = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: #2a2a3a;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        self._stack        = QStackedWidget()
        self._floor_page   = _FloorPage()
        self._measure_page = _MeasurePage()
        self._stack.addWidget(self._floor_page)
        self._stack.addWidget(self._measure_page)

        outer.addWidget(self._stack)

        # Forward inner signals
        self._floor_page.opacity_changed.connect(self.heatmap_opacity_changed)
        self._floor_page.thresholds_changed.connect(self.thresholds_changed)
        self._floor_page.calibrate_requested.connect(self.calibrate_requested)
        self._measure_page.remeasure_requested.connect(self.remeasure_requested)
        self._measure_page.delete_requested.connect(self.delete_measurement_requested)

    # ── Public API ─────────────────────────────────────────────

    def show_floor(self, floor: Optional[Floor]) -> None:
        self._floor_page.update_floor(floor)
        self._stack.setCurrentWidget(self._floor_page)

    def show_measurement(self, m: Measurement) -> None:
        self._measure_page.update_measurement(m)
        self._stack.setCurrentWidget(self._measure_page)

    def clear(self) -> None:
        self._stack.setCurrentWidget(self._floor_page)

    def update_scale(self, ppm: Optional[float]) -> None:
        self._floor_page.update_scale(ppm)
