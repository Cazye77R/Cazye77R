from __future__ import annotations

import copy
import math
import shutil
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QSize, Signal
from PySide6.QtGui import QAction, QCloseEvent, QCursor, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from models.floor import Floor
from models.measurement import Measurement
from models.project import Project
from services.scanner_worker import NetworkListWorker, ScanWorker
from services.wifi_scanner import WifiScanner
from services.exporter import ProjectExporter
from views.canvas import CanvasMode, CanvasWidget
from views.properties import PropertiesPanel
from views.side_view import SideView
from views.toolbar import ToolbarWidget


APP_STYLE = """
QMainWindow { background-color: #1e1e2e; }
QWidget {
    background-color: #1e1e2e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
}
QMenuBar { background-color: #2a2a3a; color: #e0e0e0; border-bottom: 1px solid #3a3a4a; }
QMenuBar::item { padding: 4px 10px; }
QMenuBar::item:selected { background-color: #4fc3f7; color: #1e1e2e; }
QMenu { background-color: #2a2a3a; color: #e0e0e0; border: 1px solid #3a3a4a; }
QMenu::item { padding: 4px 20px 4px 10px; }
QMenu::item:selected { background-color: #4fc3f7; color: #1e1e2e; }
QMenu::separator { height: 1px; background-color: #3a3a4a; margin: 4px 0; }
QStatusBar { background-color: #2a2a3a; color: #e0e0e0; border-top: 1px solid #3a3a4a; }
QTabBar { background-color: #2a2a3a; }
QTabBar::tab {
    background-color: #2a2a3a; color: #e0e0e0;
    padding: 5px 14px; border: 1px solid #3a3a4a;
    border-bottom: none; margin-right: 2px;
}
QTabBar::tab:selected { background-color: #4fc3f7; color: #1e1e2e; font-weight: bold; }
QTabBar::tab:hover:!selected { background-color: #353545; }
QPushButton {
    background-color: #2a2a3a; color: #e0e0e0;
    border: 1px solid #3a3a4a; padding: 3px 8px; border-radius: 3px;
}
QPushButton:hover { background-color: #4fc3f7; color: #1e1e2e; }
QPushButton:pressed { background-color: #0288d1; color: #ffffff; }
QSplitter::handle { background-color: #3a3a4a; }
QSplitter::handle:horizontal { width: 2px; }
QDockWidget { background-color: #2a2a3a; color: #e0e0e0; }
QDockWidget::title {
    background-color: #2a2a3a; color: #4fc3f7;
    padding: 4px 8px; font-weight: bold;
    border-bottom: 1px solid #3a3a4a;
}
QLineEdit {
    background-color: #2a2a3a; color: #e0e0e0;
    border: 1px solid #3a3a4a; padding: 3px 6px; border-radius: 3px;
}
QSpinBox {
    background-color: #2a2a3a; color: #e0e0e0;
    border: 1px solid #3a3a4a; padding: 2px 4px; border-radius: 3px;
}
QComboBox {
    background-color: #2a2a3a; color: #e0e0e0;
    border: 1px solid #3a3a4a; padding: 2px 6px; border-radius: 3px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #2a2a3a; color: #e0e0e0;
    border: 1px solid #3a3a4a; selection-background-color: #4fc3f7;
    selection-color: #1e1e2e;
}
"""

_TAB_MENU_STYLE = (
    "QMenu { background-color:#2a2a3a; color:#e0e0e0; border:1px solid #3a3a4a; }"
    "QMenu::item { padding:4px 20px 4px 10px; }"
    "QMenu::item:selected { background-color:#4fc3f7; color:#1e1e2e; }"
    "QMenu::separator { height:1px; background:#3a3a4a; margin:4px 0; }"
)


# ── Floor dialog ──────────────────────────────────────────────────────────────

class _FloorDialog(QDialog):
    def __init__(
        self,
        title: str = "Neue Etage",
        name: str  = "",
        level: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)

        form = QFormLayout(self)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        self._name_edit = QLineEdit(name)
        self._name_edit.setPlaceholderText("z. B. Erdgeschoss")
        form.addRow("Name:", self._name_edit)

        self._level_spin = QSpinBox()
        self._level_spin.setRange(-10, 100)
        self._level_spin.setValue(level)
        form.addRow("Stockwerk:", self._level_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def floor_name(self) -> str:
        return self._name_edit.text().strip() or "Etage"

    @property
    def floor_level(self) -> int:
        return self._level_spin.value()


# ── Tab bar ───────────────────────────────────────────────────────────────────

class _ContextTabBar(QTabBar):
    rename_requested    = Signal(int)
    duplicate_requested = Signal(int)
    move_up_requested   = Signal(int)
    move_down_requested = Signal(int)
    remove_requested    = Signal(int)

    def contextMenuEvent(self, event) -> None:
        idx = self.tabAt(event.pos())
        if idx < 0:
            return
        n   = self.count()
        menu = QMenu(self)
        menu.setStyleSheet(_TAB_MENU_STYLE)
        menu.addAction("Umbenennen").triggered.connect(
            lambda: self.rename_requested.emit(idx))
        menu.addAction("Duplizieren").triggered.connect(
            lambda: self.duplicate_requested.emit(idx))
        menu.addSeparator()
        up_act = menu.addAction("↑  Nach oben verschieben")
        up_act.setEnabled(idx > 0)
        up_act.triggered.connect(lambda: self.move_up_requested.emit(idx))
        dn_act = menu.addAction("↓  Nach unten verschieben")
        dn_act.setEnabled(idx < n - 1)
        dn_act.triggered.connect(lambda: self.move_down_requested.emit(idx))
        if n > 1:
            menu.addSeparator()
            menu.addAction("Löschen").triggered.connect(
                lambda: self.remove_requested.emit(idx))
        menu.exec(event.globalPos())


class FloorTabBar(QWidget):
    add_requested       = Signal()
    rename_requested    = Signal(int)
    duplicate_requested = Signal(int)
    move_up_requested   = Signal(int)
    move_down_requested = Signal(int)
    remove_requested    = Signal(int)
    floor_changed       = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: #2a2a3a; border-top: 1px solid #3a3a4a;")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        self.tab_bar = _ContextTabBar()
        self.tab_bar.setExpanding(False)

        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(QSize(24, 24))
        self.add_button.setToolTip("Etage hinzufügen")

        layout.addWidget(self.tab_bar)
        layout.addWidget(self.add_button)
        layout.addStretch()

        self.add_button.clicked.connect(self.add_requested)
        self.tab_bar.currentChanged.connect(self.floor_changed)
        self.tab_bar.rename_requested.connect(self.rename_requested)
        self.tab_bar.duplicate_requested.connect(self.duplicate_requested)
        self.tab_bar.move_up_requested.connect(self.move_up_requested)
        self.tab_bar.move_down_requested.connect(self.move_down_requested)
        self.tab_bar.remove_requested.connect(self.remove_requested)

    def set_floors(self, floors: list[Floor]) -> None:
        self.tab_bar.blockSignals(True)
        while self.tab_bar.count():
            self.tab_bar.removeTab(0)
        for floor in floors:
            self.tab_bar.addTab(floor.name)
        self.tab_bar.blockSignals(False)

    def current_index(self) -> int:
        return self.tab_bar.currentIndex()

    def set_current_index(self, idx: int) -> None:
        self.tab_bar.blockSignals(True)
        self.tab_bar.setCurrentIndex(idx)
        self.tab_bar.blockSignals(False)


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(900, 600)
        self.setStyleSheet(APP_STYLE)

        # ── Undo stack ─────────────────────────────────────────
        self._undo_stack = QUndoStack(self)

        # ── Project state ──────────────────────────────────────
        self._project:      Optional[Project]     = None
        self._project_path: Optional[Path]        = None

        # ── Wifi scanner & workers ─────────────────────────────
        self._wifi_scanner = WifiScanner()
        self._scan_worker:    Optional[ScanWorker]        = None
        self._net_worker:     Optional[NetworkListWorker] = None
        self._remeasure_target: Optional[Measurement]     = None

        # ── Selection state ────────────────────────────────────
        self._selected_measurement: Optional[Measurement] = None

        # ── dBm range (mirrored from canvas/properties for side view) ─
        self._min_dbm: float = -90.0
        self._max_dbm: float = -30.0

        self._setup_menubar()
        self._setup_central_widget()
        self._setup_side_view()      # creates _side_view + _side_dock
        self._setup_statusbar()

        # ── Wire canvas ────────────────────────────────────────
        cv = self._canvas_widget
        cv.set_undo_stack(self._undo_stack)
        cv.zoom_changed.connect(self._on_zoom_changed)
        cv.pending_changed.connect(self._on_pending_changed)
        cv.measurement_selected.connect(self._on_measurement_selected)
        cv.router_changed.connect(self._on_router_changed)
        cv.heatmap_computing.connect(self._on_heatmap_computing)

        # ── Wire toolbar ───────────────────────────────────────
        tb = self._toolbar_widget
        tb.mode_changed.connect(cv.set_mode)
        tb.measure_triggered.connect(self._on_measure_triggered)
        tb.snap_points_changed.connect(cv.set_snap_points)
        tb.grid_snap_changed.connect(cv.set_snap_grid)
        tb.grid_size_changed.connect(cv.set_grid_size)

        # ── Wire floor tab bar ─────────────────────────────────
        ftb = self._floor_tab_bar
        ftb.add_requested.connect(self._on_floor_add)
        ftb.floor_changed.connect(self._on_tab_changed)
        ftb.rename_requested.connect(self._on_floor_rename)
        ftb.duplicate_requested.connect(self._on_floor_duplicate)
        ftb.move_up_requested.connect(self._on_floor_move_up)
        ftb.move_down_requested.connect(self._on_floor_move_down)
        ftb.remove_requested.connect(self._on_floor_remove)

        # ── Wire properties panel ──────────────────────────────
        pp = self._properties_panel
        pp.remeasure_requested.connect(self._on_remeasure_requested)
        pp.delete_measurement_requested.connect(self._on_delete_measurement)
        pp.heatmap_opacity_changed.connect(self._on_opacity_changed)
        pp.thresholds_changed.connect(cv.set_dbm_range)
        pp.thresholds_changed.connect(self._on_thresholds_changed)

        # ── Dirty title ────────────────────────────────────────
        self._undo_stack.indexChanged.connect(lambda _: self._update_title())

        # ── Startup ────────────────────────────────────────────
        self._create_default_project()
        self._refresh_network_list()

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()

        datei = menubar.addMenu("Datei")
        datei.addAction(self._make_action("Neues Projekt", self._new_project))
        datei.addAction(self._make_action("Projekt öffnen …", self._open_project))
        datei.addAction(self._make_action("Projekt speichern", self._save_project,
                                          QKeySequence("Ctrl+S")))
        datei.addSeparator()
        export_menu = datei.addMenu("Exportieren")
        export_menu.addAction(self._make_action(
            "PNG (aktuelle Etage) …",  self._export_png))
        export_menu.addAction(self._make_action(
            "PDF (ganzes Projekt) …",  self._export_pdf))
        export_menu.addAction(self._make_action(
            "JSON …",                  self._export_json))

        bearbeiten = menubar.addMenu("Bearbeiten")
        undo_action = self._undo_stack.createUndoAction(self, "Rückgängig")
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        bearbeiten.addAction(undo_action)
        redo_action = self._undo_stack.createRedoAction(self, "Wiederholen")
        redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        bearbeiten.addAction(redo_action)

        self._ansicht_menu = menubar.addMenu("Ansicht")
        self._heatmap_action = QAction("Heatmap ein/aus", self)
        self._heatmap_action.setCheckable(True)
        self._heatmap_action.setChecked(True)
        self._heatmap_action.triggered.connect(self._toggle_heatmap)
        self._ansicht_menu.addAction(self._heatmap_action)

        self._grid_action = QAction("Raster ein/aus", self)
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(False)
        self._grid_action.triggered.connect(self._toggle_grid)
        self._ansicht_menu.addAction(self._grid_action)

    def _make_action(
        self, label: str, slot, shortcut: QKeySequence | None = None
    ) -> QAction:
        action = QAction(label, self)
        action.triggered.connect(slot)
        if shortcut is not None:
            action.setShortcut(shortcut)
        return action

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------

    def _setup_central_widget(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal)

        self._toolbar_widget = ToolbarWidget()
        self._toolbar_widget.setFixedWidth(150)

        self._canvas_widget = CanvasWidget()

        self._properties_panel = PropertiesPanel()
        self._properties_panel.setFixedWidth(250)

        self._splitter.addWidget(self._toolbar_widget)
        self._splitter.addWidget(self._canvas_widget)
        self._splitter.addWidget(self._properties_panel)
        self._splitter.setHandleWidth(2)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, False)

        root_layout.addWidget(self._splitter, stretch=1)

        self._floor_tab_bar = FloorTabBar()
        root_layout.addWidget(self._floor_tab_bar)

    # ------------------------------------------------------------------
    # Side view dock
    # ------------------------------------------------------------------

    def _setup_side_view(self) -> None:
        self._side_view = SideView()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._side_view)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: #2a2a3a; }"
        )

        self._side_dock = QDockWidget("Seitenansicht", self)
        self._side_dock.setWidget(scroll)
        self._side_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._side_dock.setMinimumWidth(180)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._side_dock)

        # Add toggle action to Ansicht menu
        side_action = self._side_dock.toggleViewAction()
        side_action.setText("Seitenansicht ein/aus")
        self._ansicht_menu.addSeparator()
        self._ansicht_menu.addAction(side_action)

        self._side_view.measurement_clicked.connect(self._on_side_view_clicked)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _setup_statusbar(self) -> None:
        # Left: zoom · floor · router distance
        self._zoom_label = QLabel("Zoom: 100%")
        self._zoom_label.setStyleSheet("padding: 0 8px; color: #9090a0;")
        self.statusBar().addWidget(self._zoom_label)

        self._floor_label = QLabel("Etage: —")
        self._floor_label.setStyleSheet("padding: 0 8px; color: #b0b8d0;")
        self.statusBar().addWidget(self._floor_label)

        self._router_dist_label = QLabel("")
        self._router_dist_label.setStyleSheet("padding: 0 8px; color: #4fc3f7;")
        self.statusBar().addWidget(self._router_dist_label)

        # Right: SSID filter + signal info
        ssid_widget = QWidget()
        ssid_widget.setStyleSheet("background: transparent;")
        ssid_layout = QHBoxLayout(ssid_widget)
        ssid_layout.setContentsMargins(4, 0, 8, 0)
        ssid_layout.setSpacing(6)

        ssid_layout.addWidget(QLabel("SSID-Filter:"))

        self._ssid_combo = QComboBox()
        self._ssid_combo.setMinimumWidth(150)
        self._ssid_combo.setMaximumWidth(240)
        self._ssid_combo.addItem("Alle Netzwerke")
        self._ssid_combo.currentTextChanged.connect(self._on_ssid_filter_changed)
        ssid_layout.addWidget(self._ssid_combo)

        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setFixedSize(22, 22)
        self._refresh_btn.setToolTip("Netzwerkliste aktualisieren")
        self._refresh_btn.clicked.connect(self._refresh_network_list)
        ssid_layout.addWidget(self._refresh_btn)

        self._signal_label = QLabel("Signal: —")
        self._signal_label.setStyleSheet("padding: 0 4px; color: #9090a0;")
        ssid_layout.addWidget(self._signal_label)

        self.statusBar().addPermanentWidget(ssid_widget)

    def _on_zoom_changed(self, percent: float) -> None:
        self._zoom_label.setText(f"Zoom: {percent:.0f}%")

    def update_status(self, ssid: str = "—", signal: str = "—", band: str = "—") -> None:
        self._signal_label.setText(
            f"  {ssid}  |  {signal}  |  {band}"
        )

    # ------------------------------------------------------------------
    # SSID dropdown
    # ------------------------------------------------------------------

    def _refresh_network_list(self) -> None:
        if self._net_worker is not None and self._net_worker.isRunning():
            return
        self._refresh_btn.setEnabled(False)
        self._net_worker = NetworkListWorker(self._wifi_scanner)
        self._net_worker.result_ready.connect(self._on_network_list_ready)
        self._net_worker.finished.connect(lambda: self._refresh_btn.setEnabled(True))
        self._net_worker.start()

    def _on_network_list_ready(self, nets: list, connected: str) -> None:
        current = self._ssid_combo.currentText()
        fresh_start = (current == "Alle Netzwerke" and self._ssid_combo.count() == 1)
        self._ssid_combo.blockSignals(True)
        self._ssid_combo.clear()
        self._ssid_combo.addItem("Alle Netzwerke")
        for net in nets:
            ssid = net.get("ssid", "")
            if ssid and self._ssid_combo.findText(ssid) < 0:
                self._ssid_combo.addItem(ssid)
        if fresh_start and connected:
            idx = self._ssid_combo.findText(connected)
            self._ssid_combo.setCurrentIndex(max(0, idx))
        else:
            idx = self._ssid_combo.findText(current)
            self._ssid_combo.setCurrentIndex(max(0, idx))
        self._ssid_combo.blockSignals(False)

    def _on_ssid_filter_changed(self, text: str) -> None:
        ssid = None if text == "Alle Netzwerke" else text
        self._canvas_widget.set_ssid_filter(ssid)

    # ------------------------------------------------------------------
    # Measurement workflow
    # ------------------------------------------------------------------

    def _on_pending_changed(self, has_pending: bool) -> None:
        self._toolbar_widget.set_measure_enabled(has_pending)

    def _on_measure_triggered(self) -> None:
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        self._toolbar_widget.set_measure_running(True)
        self._scan_worker = ScanWorker(self._wifi_scanner, count=5, interval=0.4)
        self._scan_worker.result_ready.connect(self._on_scan_result)
        self._scan_worker.error_occurred.connect(self._on_scan_error)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_result(self, result) -> None:
        pos = self._canvas_widget.pending_measure_pos
        if pos is None:
            return

        if self._remeasure_target is not None:
            self._canvas_widget.remove_measurement_item(self._remeasure_target)
            self._remeasure_target = None

        m = Measurement(
            x=pos.x(),
            y=pos.y(),
            dbm=result.dbm,
            signal_percent=result.signal_percent,
            ssid=result.ssid,
            channel=result.channel,
            band=result.band,
            std_deviation=result.std_deviation,
            bssid=result.bssid,
        )
        self._canvas_widget.place_measurement(m)
        self._properties_panel.show_measurement(m)
        self._refresh_side_view()
        self.update_status(
            ssid=result.ssid,
            signal=f"{result.dbm:.1f} dBm  ({result.signal_percent} %)",
            band=result.band,
        )
        # Auto-add SSID to dropdown if new
        if result.ssid and self._ssid_combo.findText(result.ssid) < 0:
            self._ssid_combo.addItem(result.ssid)

    def _on_scan_error(self, msg: str) -> None:
        QMessageBox.warning(self, "WLAN-Messung fehlgeschlagen", msg)

    def _on_scan_finished(self) -> None:
        self._toolbar_widget.set_measure_running(False)
        # Re-enable MESSEN if there is still a pending position
        has_pending = self._canvas_widget.pending_measure_pos is not None
        self._toolbar_widget.set_measure_enabled(has_pending)

    def _on_measurement_selected(self, m) -> None:
        self._selected_measurement = m
        if m is not None:
            self._properties_panel.show_measurement(m)
        else:
            self._properties_panel.show_floor(self._canvas_widget.current_floor())
        self._update_router_distance()

    def _on_remeasure_requested(self, m: Measurement) -> None:
        self._remeasure_target = m
        # Switch to MEASURE mode and pre-place the pending marker
        self._toolbar_widget.set_active_mode(CanvasMode.MEASURE)
        self._canvas_widget.set_mode(CanvasMode.MEASURE)
        self._canvas_widget.place_pending_at(QPointF(m.x, m.y))

    def _on_delete_measurement(self, m: Measurement) -> None:
        self._canvas_widget.remove_measurement_item(m)
        self._properties_panel.show_floor(self._canvas_widget.current_floor())
        self._refresh_side_view()

    def _on_router_changed(self, _pos) -> None:
        self._update_router_distance()
        self._refresh_side_view()

    def _update_router_distance(self) -> None:
        m     = self._selected_measurement
        floor = self._canvas_widget.current_floor()
        if m is None or floor is None or floor.router_position is None:
            self._router_dist_label.setText("")
            return
        rx, ry   = floor.router_position
        dist_px  = math.sqrt((m.x - rx) ** 2 + (m.y - ry) ** 2)
        self._router_dist_label.setText(f"📡 {dist_px:.0f} px")

    def _on_opacity_changed(self, opacity: int) -> None:
        self._canvas_widget.set_heatmap_opacity(opacity)

    def _on_thresholds_changed(self, min_dbm: float, max_dbm: float) -> None:
        self._min_dbm = min_dbm
        self._max_dbm = max_dbm
        self._side_view.set_dbm_range(min_dbm, max_dbm)

    def _refresh_side_view(self) -> None:
        if self._project is None:
            return
        self._side_view.set_project(
            self._project.floors, self._min_dbm, self._max_dbm
        )

    def _on_side_view_clicked(self, floor: Floor, m: Measurement) -> None:
        if self._project is None:
            return
        try:
            idx = self._project.floors.index(floor)
        except ValueError:
            return
        current_idx = self._floor_tab_bar.current_index()
        if idx != current_idx:
            self._floor_tab_bar.set_current_index(idx)
            self._on_tab_changed(idx)
        self._canvas_widget.scroll_to_measurement(m)
        self._selected_measurement = m
        self._properties_panel.show_measurement(m)
        self._update_router_distance()

    def _on_heatmap_computing(self, computing: bool) -> None:
        if computing:
            self._signal_label.setText("  Heatmap wird berechnet…")
        else:
            self._signal_label.setText("Signal: —")

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    def _create_default_project(self) -> None:
        project = Project(name="Neues Projekt")
        project.floors.append(Floor(name="Erdgeschoss", level=0))
        self._setup_project(project)

    def _setup_project(self, project: Project, path: Optional[Path] = None) -> None:
        self._project      = project
        self._project_path = path
        self._undo_stack.clear()
        self._undo_stack.setClean()
        project.floors.sort(key=lambda f: f.level)
        self._sync_tabs()
        if project.floors:
            floor = project.floors[0]
            self._canvas_widget.set_active_floor(floor)
            self._properties_panel.show_floor(floor)
        self._floor_tab_bar.set_current_index(0)
        self._update_floor_label()
        self._update_title()
        self._refresh_side_view()

    def _sync_tabs(self) -> None:
        floors = self._project.floors if self._project else []
        self._floor_tab_bar.set_floors(floors)

    def _on_tab_changed(self, idx: int) -> None:
        if self._project and 0 <= idx < len(self._project.floors):
            floor = self._project.floors[idx]
            self._selected_measurement = None
            self._canvas_widget.set_active_floor(floor)
            self._properties_panel.show_floor(floor)
            self._update_router_distance()
            self._update_floor_label()

    def _update_floor_label(self) -> None:
        floor = self._canvas_widget.current_floor()
        if floor is None:
            self._floor_label.setText("Etage: —")
        else:
            self._floor_label.setText(f"Etage: {floor.name}")

    # ------------------------------------------------------------------
    # Floor operations
    # ------------------------------------------------------------------

    def _on_floor_add(self) -> None:
        if self._project is None:
            return
        next_level = (max(f.level for f in self._project.floors) + 1
                      if self._project.floors else 0)
        dlg = _FloorDialog(title="Neue Etage", level=next_level, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        floor = Floor(name=dlg.floor_name, level=dlg.floor_level)
        self._project.floors.append(floor)
        self._project.floors.sort(key=lambda f: f.level)
        self._sync_tabs()
        idx = self._project.floors.index(floor)
        self._floor_tab_bar.set_current_index(idx)
        self._canvas_widget.set_active_floor(floor)
        self._properties_panel.show_floor(floor)
        self._refresh_side_view()

    def _on_floor_rename(self, idx: int) -> None:
        if not self._project or idx >= len(self._project.floors):
            return
        floor = self._project.floors[idx]
        name, ok = QInputDialog.getText(
            self, "Etage umbenennen", "Name:", text=floor.name
        )
        if ok and name.strip():
            floor.name = name.strip()
            self._sync_tabs()
            self._floor_tab_bar.set_current_index(idx)
            self._update_floor_label()
            self._refresh_side_view()

    def _on_floor_duplicate(self, idx: int) -> None:
        if not self._project or idx >= len(self._project.floors):
            return
        src   = self._project.floors[idx]
        elems = copy.deepcopy(src.elements)
        for e in elems:
            e["id"] = str(uuid.uuid4())
        new_floor = Floor(
            name=f"{src.name} (Kopie)",
            level=src.level + 1,
            background_image=src.background_image,
            bg_offset=src.bg_offset,
            bg_scale=src.bg_scale,
            elements=elems,
        )
        self._project.floors.append(new_floor)
        self._project.floors.sort(key=lambda f: f.level)
        self._sync_tabs()
        new_idx = self._project.floors.index(new_floor)
        self._floor_tab_bar.set_current_index(new_idx)
        self._canvas_widget.set_active_floor(new_floor)
        self._properties_panel.show_floor(new_floor)
        self._refresh_side_view()

    def _on_floor_move_up(self, idx: int) -> None:
        """Move the floor at *idx* one position to the left (lower tab index)."""
        if not self._project or idx <= 0:
            return
        self._swap_floors(idx, idx - 1)

    def _on_floor_move_down(self, idx: int) -> None:
        """Move the floor at *idx* one position to the right (higher tab index)."""
        if not self._project or idx >= len(self._project.floors) - 1:
            return
        self._swap_floors(idx, idx + 1)

    def _swap_floors(self, a: int, b: int) -> None:
        """Swap floors at positions *a* and *b*, keep the active floor selected."""
        floors = self._project.floors          # type: ignore[union-attr]
        active = self._canvas_widget.current_floor()

        floors[a], floors[b] = floors[b], floors[a]
        # Re-number levels to match new positions so save/load preserves order
        floors[a].level, floors[b].level = floors[b].level, floors[a].level

        self._sync_tabs()
        # Restore selection on the previously active floor
        new_idx = floors.index(active) if active in floors else min(a, b)
        self._floor_tab_bar.set_current_index(new_idx)
        self._update_floor_label()
        self._refresh_side_view()

    def _on_floor_remove(self, idx: int) -> None:
        if not self._project or len(self._project.floors) <= 1:
            return
        floor = self._project.floors[idx]
        resp = QMessageBox.question(
            self, "Etage löschen",
            f"Etage \"{floor.name}\" wirklich löschen?\n"
            "Alle Daten dieser Etage gehen verloren.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        self._project.floors.pop(idx)
        self._sync_tabs()
        new_idx = min(idx, len(self._project.floors) - 1)
        self._floor_tab_bar.set_current_index(new_idx)
        new_floor = self._project.floors[new_idx]
        self._canvas_widget.set_active_floor(new_floor)
        self._properties_panel.show_floor(new_floor)
        self._refresh_side_view()

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _new_project(self) -> None:
        if not self._confirm_discard():
            return
        name, ok = QInputDialog.getText(self, "Neues Projekt", "Projektname:")
        if not ok or not name.strip():
            return
        project = Project(name=name.strip())
        project.floors.append(Floor(name="Erdgeschoss", level=0))
        self._setup_project(project)

    def _open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Projekt öffnen", "",
            "WiFi Heatmap (*.wifiheat);;Alle Dateien (*)",
        )
        if not path:
            return
        try:
            project = Project.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Fehler",
                                 f"Projekt konnte nicht geladen werden:\n{exc}")
            return
        project_dir = Path(path).parent
        for floor in project.floors:
            if floor.background_image:
                candidate = project_dir / floor.background_image
                floor.background_image = str(candidate) if candidate.exists() else None
        self._setup_project(project, Path(path))

    def _save_project(self) -> None:
        if self._project is None:
            return
        if self._project_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Projekt speichern", self._project.name,
                "WiFi Heatmap (*.wifiheat);;Alle Dateien (*)",
            )
            if not path:
                return
            if not path.endswith(".wifiheat"):
                path += ".wifiheat"
            self._project_path = Path(path)

        project_dir = self._project_path.parent
        images_dir  = project_dir / "images"
        images_dir.mkdir(exist_ok=True)

        for floor in self._project.floors:
            if floor.background_image:
                src = Path(floor.background_image)
                if src.is_absolute() and src.exists():
                    dst = images_dir / src.name
                    if src.resolve() != dst.resolve():
                        shutil.copy2(str(src), str(dst))
                    floor.background_image = f"images/{src.name}"

        try:
            self._project.save(self._project_path)
        except Exception as exc:
            QMessageBox.critical(self, "Fehler",
                                 f"Projekt konnte nicht gespeichert werden:\n{exc}")
            return
        self._undo_stack.setClean()
        self._update_title()

    def _confirm_discard(self) -> bool:
        if self._project is None or self._undo_stack.isClean():
            return True
        resp = QMessageBox.question(
            self, "Ungespeicherte Änderungen",
            "Das aktuelle Projekt hat ungespeicherte Änderungen.\nMöchten Sie speichern?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if resp == QMessageBox.StandardButton.Save:
            self._save_project()
            return self._undo_stack.isClean()
        return resp == QMessageBox.StandardButton.Discard

    # ------------------------------------------------------------------
    # Title / close
    # ------------------------------------------------------------------

    def _update_title(self) -> None:
        name  = self._project.name if self._project else "Unbenannt"
        dirty = self._project is not None and not self._undo_stack.isClean()
        self.setWindowTitle(f"{'* ' if dirty else ''}WiFi Heatmap — {name}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # View toggles
    # ------------------------------------------------------------------

    def _toggle_heatmap(self, checked: bool) -> None:
        self._canvas_widget.set_heatmap_visible(checked)

    def _toggle_grid(self, checked: bool) -> None:
        self._canvas_widget.set_show_grid(checked)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_json(self) -> None:
        if self._project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "JSON exportieren",
            self._project.name + ".wifiheat",
            "WiFi Heatmap JSON (*.wifiheat);;Alle Dateien (*)",
        )
        if not path:
            return
        try:
            ProjectExporter.export_json(self._project, path)
        except Exception as exc:
            QMessageBox.critical(self, "Export fehlgeschlagen", str(exc))

    def _export_png(self) -> None:
        if self._project is None:
            return
        floor = self._canvas_widget.current_floor()
        if floor is None:
            QMessageBox.information(self, "Export", "Keine aktive Etage.")
            return

        # ── Scale dialog ──────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("PNG-Auflösung")
        dlg.setFixedWidth(260)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(8)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addWidget(QLabel("Ausgabe-Auflösung:"))

        grp = QGroupBox()
        grp.setFlat(True)
        glayout = QVBoxLayout(grp)
        glayout.setSpacing(4)

        bg   = QButtonGroup(dlg)
        opts = [("1× (Originalgröße)", 1),
                ("2× (doppelte Auflösung)", 2),
                ("4× (vierfache Auflösung)", 4)]
        radios: list[tuple[QRadioButton, int]] = []
        for label, scale in opts:
            rb = QRadioButton(label)
            if scale == 1:
                rb.setChecked(True)
            bg.addButton(rb)
            glayout.addWidget(rb)
            radios.append((rb, scale))

        lay.addWidget(grp)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        scale = next((s for rb, s in radios if rb.isChecked()), 1)

        # ── File dialog ───────────────────────────────────────────
        path, _ = QFileDialog.getSaveFileName(
            self, "PNG exportieren",
            f"{self._project.name}_{floor.name}.png",
            "PNG-Bild (*.png);;Alle Dateien (*)",
        )
        if not path:
            return

        # ── Render ────────────────────────────────────────────────
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self._canvas_widget.scene().clearSelection()
            source_rect = self._canvas_widget.get_render_rect()
            ProjectExporter.export_png(
                self._canvas_widget.scene(),
                source_rect,
                floor,
                path,
                self._min_dbm,
                self._max_dbm,
                scale=scale,
            )
        except Exception as exc:
            QMessageBox.critical(self, "PNG-Export fehlgeschlagen", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def _export_pdf(self) -> None:
        if self._project is None:
            return
        if not self._project.floors:
            QMessageBox.information(self, "Export", "Projekt hat keine Etagen.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "PDF exportieren",
            self._project.name + ".pdf",
            "PDF-Dokument (*.pdf);;Alle Dateien (*)",
        )
        if not path:
            return

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            # Remember which floor is active so we can restore it
            active_floor = self._canvas_widget.current_floor()

            # Render each floor to a QImage
            floor_images: list[tuple] = []
            for idx, floor in enumerate(self._project.floors):
                self._floor_tab_bar.set_current_index(idx)
                self._canvas_widget.set_active_floor(floor)
                QApplication.processEvents()   # allow scene to settle
                self._canvas_widget.scene().clearSelection()
                source_rect = self._canvas_widget.get_render_rect()
                img = ProjectExporter.render_floor_image(
                    self._canvas_widget.scene(),
                    source_rect,
                    floor,
                    self._min_dbm,
                    self._max_dbm,
                    scale=1,
                )
                floor_images.append((floor, img))

            # Restore original floor
            if active_floor is not None:
                self._canvas_widget.set_active_floor(active_floor)
                idx = (self._project.floors.index(active_floor)
                       if active_floor in self._project.floors else 0)
                self._floor_tab_bar.set_current_index(idx)

            # Render side view (full height)
            sv_img = self._side_view.render_to_image()

            ProjectExporter.export_pdf(
                self._project,
                floor_images,
                path,
                self._min_dbm,
                self._max_dbm,
                critical_threshold=-75.0,
                side_view_image=sv_img,
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF-Export fehlgeschlagen", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
