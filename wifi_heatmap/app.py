from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from views.canvas import CanvasWidget
from views.properties import PropertiesPanel
from views.toolbar import ToolbarWidget

APP_STYLE = """
QMainWindow {
    background-color: #1e1e2e;
}
QWidget {
    background-color: #1e1e2e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
}
QMenuBar {
    background-color: #2a2a3a;
    color: #e0e0e0;
    border-bottom: 1px solid #3a3a4a;
}
QMenuBar::item {
    padding: 4px 10px;
}
QMenuBar::item:selected {
    background-color: #4fc3f7;
    color: #1e1e2e;
}
QMenu {
    background-color: #2a2a3a;
    color: #e0e0e0;
    border: 1px solid #3a3a4a;
}
QMenu::item {
    padding: 4px 20px 4px 10px;
}
QMenu::item:selected {
    background-color: #4fc3f7;
    color: #1e1e2e;
}
QMenu::separator {
    height: 1px;
    background-color: #3a3a4a;
    margin: 4px 0;
}
QStatusBar {
    background-color: #2a2a3a;
    color: #e0e0e0;
    border-top: 1px solid #3a3a4a;
}
QTabBar {
    background-color: #2a2a3a;
}
QTabBar::tab {
    background-color: #2a2a3a;
    color: #e0e0e0;
    padding: 5px 14px;
    border: 1px solid #3a3a4a;
    border-bottom: none;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #4fc3f7;
    color: #1e1e2e;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #353545;
}
QPushButton {
    background-color: #2a2a3a;
    color: #e0e0e0;
    border: 1px solid #3a3a4a;
    padding: 3px 8px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #4fc3f7;
    color: #1e1e2e;
}
QPushButton:pressed {
    background-color: #0288d1;
    color: #ffffff;
}
QSplitter::handle {
    background-color: #3a3a4a;
}
QSplitter::handle:horizontal {
    width: 2px;
}
"""


class FloorTabBar(QWidget):
    """Tab bar for floor navigation with an inline '+' add button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: #2a2a3a; border-top: 1px solid #3a3a4a;")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.addTab("Erdgeschoss")

        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(QSize(24, 24))
        self.add_button.setToolTip("Etage hinzufügen")
        self.add_button.clicked.connect(self._add_floor)

        layout.addWidget(self.tab_bar)
        layout.addWidget(self.add_button)
        layout.addStretch()

    def _add_floor(self) -> None:
        count = self.tab_bar.count()
        if count == 1:
            label = "Obergeschoss"
        else:
            label = f"Etage {count}"
        self.tab_bar.addTab(label)
        self.tab_bar.setCurrentIndex(self.tab_bar.count() - 1)

    def current_index(self) -> int:
        return self.tab_bar.currentIndex()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WiFi Heatmap")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(APP_STYLE)

        self._setup_menubar()
        self._setup_central_widget()
        self._setup_statusbar()
        self._canvas_widget.zoom_changed.connect(self._on_zoom_changed)
        self._floor_tab_bar.tab_bar.currentChanged.connect(self._canvas_widget.load_floor)
        self._canvas_widget.load_floor(0)

        tb = self._toolbar_widget
        cv = self._canvas_widget
        tb.mode_changed.connect(cv.set_mode)
        tb.snap_points_changed.connect(cv.set_snap_points)
        tb.grid_snap_changed.connect(cv.set_snap_grid)
        tb.grid_size_changed.connect(cv.set_grid_size)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()

        # --- Datei ---
        datei = menubar.addMenu("Datei")
        datei.addAction(self._make_action("Neues Projekt", self._new_project))
        datei.addAction(self._make_action("Projekt öffnen …", self._open_project))
        datei.addAction(self._make_action("Projekt speichern", self._save_project))
        datei.addSeparator()

        export_menu = datei.addMenu("Exportieren")
        export_menu.addAction(self._make_action("PNG", lambda: self._export("png")))
        export_menu.addAction(self._make_action("PDF", lambda: self._export("pdf")))
        export_menu.addAction(self._make_action("JSON", lambda: self._export("json")))

        # --- Bearbeiten ---
        bearbeiten = menubar.addMenu("Bearbeiten")

        undo = self._make_action("Rückgängig", self._undo)
        undo.setShortcut(QKeySequence("Ctrl+Z"))
        bearbeiten.addAction(undo)

        redo = self._make_action("Wiederholen", self._redo)
        redo.setShortcut(QKeySequence("Ctrl+Y"))
        bearbeiten.addAction(redo)

        # --- Ansicht ---
        ansicht = menubar.addMenu("Ansicht")

        self._side_view_action = QAction("Seitenansicht ein/aus", self)
        self._side_view_action.setCheckable(True)
        self._side_view_action.setChecked(False)
        self._side_view_action.triggered.connect(self._toggle_side_view)
        ansicht.addAction(self._side_view_action)

        self._heatmap_action = QAction("Heatmap ein/aus", self)
        self._heatmap_action.setCheckable(True)
        self._heatmap_action.setChecked(True)
        self._heatmap_action.triggered.connect(self._toggle_heatmap)
        ansicht.addAction(self._heatmap_action)

        self._grid_action = QAction("Raster ein/aus", self)
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(False)
        self._grid_action.triggered.connect(self._toggle_grid)
        ansicht.addAction(self._grid_action)

    def _make_action(self, label: str, slot) -> QAction:
        action = QAction(label, self)
        action.triggered.connect(slot)
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

        # Three-column splitter
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

        # Floor tab bar sits between canvas and status bar
        self._floor_tab_bar = FloorTabBar()
        root_layout.addWidget(self._floor_tab_bar)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _setup_statusbar(self) -> None:
        self._zoom_label = QLabel("Zoom: 100%")
        self._zoom_label.setStyleSheet("padding: 0 8px; color: #9090a0;")
        self.statusBar().addWidget(self._zoom_label)

        self._status_label = QLabel("SSID: — | Signal: — | Band: —")
        self._status_label.setStyleSheet("padding: 0 8px;")
        self.statusBar().addPermanentWidget(self._status_label)

    def _on_zoom_changed(self, percent: float) -> None:
        self._zoom_label.setText(f"Zoom: {percent:.0f}%")

    def update_status(
        self,
        ssid: str = "—",
        signal: str = "—",
        band: str = "—",
    ) -> None:
        self._status_label.setText(f"SSID: {ssid} | Signal: {signal} | Band: {band}")

    # ------------------------------------------------------------------
    # Menu slots (stubs)
    # ------------------------------------------------------------------

    def _new_project(self) -> None:
        pass

    def _open_project(self) -> None:
        pass

    def _save_project(self) -> None:
        pass

    def _export(self, fmt: str) -> None:
        pass

    def _undo(self) -> None:
        pass

    def _redo(self) -> None:
        pass

    def _toggle_side_view(self, checked: bool) -> None:
        pass

    def _toggle_heatmap(self, checked: bool) -> None:
        pass

    def _toggle_grid(self, checked: bool) -> None:
        self._canvas_widget.set_show_grid(checked)
