from __future__ import annotations

import copy
import shutil
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from models.floor import Floor
from models.project import Project
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
QLineEdit {
    background-color: #2a2a3a;
    color: #e0e0e0;
    border: 1px solid #3a3a4a;
    padding: 3px 6px;
    border-radius: 3px;
}
QSpinBox {
    background-color: #2a2a3a;
    color: #e0e0e0;
    border: 1px solid #3a3a4a;
    padding: 2px 4px;
    border-radius: 3px;
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
    """Dialog for creating or editing a floor (name + level number)."""

    def __init__(
        self,
        title: str = "Neue Etage",
        name: str = "",
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
        self._level_spin.setToolTip("Stockwerk-Nummer (0 = Erdgeschoss, 1 = Obergeschoss, …)")
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
    """QTabBar that emits context-menu signals instead of handling them directly."""

    rename_requested    = Signal(int)
    duplicate_requested = Signal(int)
    remove_requested    = Signal(int)

    def contextMenuEvent(self, event) -> None:
        idx = self.tabAt(event.pos())
        if idx < 0:
            return
        menu = QMenu(self)
        menu.setStyleSheet(_TAB_MENU_STYLE)
        menu.addAction("Umbenennen").triggered.connect(
            lambda: self.rename_requested.emit(idx))
        menu.addAction("Duplizieren").triggered.connect(
            lambda: self.duplicate_requested.emit(idx))
        if self.count() > 1:
            menu.addSeparator()
            act = menu.addAction("Löschen")
            act.triggered.connect(lambda: self.remove_requested.emit(idx))
        menu.exec(event.globalPos())


class FloorTabBar(QWidget):
    """Tab bar for floor navigation — supports add, rename, duplicate, delete."""

    add_requested       = Signal()
    rename_requested    = Signal(int)
    duplicate_requested = Signal(int)
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
        self.tab_bar.remove_requested.connect(self.remove_requested)

    def set_floors(self, floors: list[Floor]) -> None:
        """Rebuild tabs to match the given floor list (no signals emitted)."""
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

        # ── Undo stack (created first so menubar can reference it) ─
        self._undo_stack = QUndoStack(self)

        # ── Project state ──────────────────────────────────────────
        self._project:      Optional[Project] = None
        self._project_path: Optional[Path]    = None

        self._setup_menubar()
        self._setup_central_widget()
        self._setup_statusbar()

        # ── Wire canvas ────────────────────────────────────────────
        self._canvas_widget.set_undo_stack(self._undo_stack)
        self._canvas_widget.zoom_changed.connect(self._on_zoom_changed)

        # ── Wire toolbar ───────────────────────────────────────────
        tb = self._toolbar_widget
        cv = self._canvas_widget
        tb.mode_changed.connect(cv.set_mode)
        tb.snap_points_changed.connect(cv.set_snap_points)
        tb.grid_snap_changed.connect(cv.set_snap_grid)
        tb.grid_size_changed.connect(cv.set_grid_size)

        # ── Wire floor tab bar ─────────────────────────────────────
        ftb = self._floor_tab_bar
        ftb.add_requested.connect(self._on_floor_add)
        ftb.floor_changed.connect(self._on_tab_changed)
        ftb.rename_requested.connect(self._on_floor_rename)
        ftb.duplicate_requested.connect(self._on_floor_duplicate)
        ftb.remove_requested.connect(self._on_floor_remove)

        # ── Update title on undo-index change ──────────────────────
        self._undo_stack.indexChanged.connect(lambda _: self._update_title())

        # ── Start with a default empty project ─────────────────────
        self._create_default_project()

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()

        # --- Datei ---
        datei = menubar.addMenu("Datei")
        datei.addAction(self._make_action("Neues Projekt", self._new_project))
        datei.addAction(self._make_action("Projekt öffnen …", self._open_project))
        datei.addAction(self._make_action("Projekt speichern", self._save_project,
                                          QKeySequence("Ctrl+S")))
        datei.addSeparator()

        export_menu = datei.addMenu("Exportieren")
        export_menu.addAction(self._make_action("PNG",  lambda: self._export("png")))
        export_menu.addAction(self._make_action("PDF",  lambda: self._export("pdf")))
        export_menu.addAction(self._make_action("JSON", lambda: self._export("json")))

        # --- Bearbeiten ---
        bearbeiten = menubar.addMenu("Bearbeiten")

        undo_action = self._undo_stack.createUndoAction(self, "Rückgängig")
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        bearbeiten.addAction(undo_action)

        redo_action = self._undo_stack.createRedoAction(self, "Wiederholen")
        redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        bearbeiten.addAction(redo_action)

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
    # Project management
    # ------------------------------------------------------------------

    def _create_default_project(self) -> None:
        project = Project(name="Neues Projekt")
        project.floors.append(Floor(name="Erdgeschoss", level=0))
        self._setup_project(project)

    def _setup_project(
        self, project: Project, path: Optional[Path] = None
    ) -> None:
        self._project      = project
        self._project_path = path
        self._undo_stack.clear()
        self._undo_stack.setClean()
        project.floors.sort(key=lambda f: f.level)
        self._sync_tabs()
        if project.floors:
            self._canvas_widget.set_active_floor(project.floors[0])
        self._floor_tab_bar.set_current_index(0)
        self._update_title()

    def _sync_tabs(self) -> None:
        floors = self._project.floors if self._project else []
        self._floor_tab_bar.set_floors(floors)

    def _on_tab_changed(self, idx: int) -> None:
        if self._project and 0 <= idx < len(self._project.floors):
            self._canvas_widget.set_active_floor(self._project.floors[idx])

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

    def _on_floor_remove(self, idx: int) -> None:
        if not self._project or len(self._project.floors) <= 1:
            return
        floor = self._project.floors[idx]
        resp = QMessageBox.question(
            self,
            "Etage löschen",
            f"Etage \"{floor.name}\" wirklich löschen?\nAlle Daten dieser Etage gehen verloren.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        self._project.floors.pop(idx)
        self._sync_tabs()
        new_idx = min(idx, len(self._project.floors) - 1)
        self._floor_tab_bar.set_current_index(new_idx)
        self._canvas_widget.set_active_floor(self._project.floors[new_idx])

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
            QMessageBox.critical(
                self, "Fehler",
                f"Projekt konnte nicht geladen werden:\n{exc}",
            )
            return
        project_dir = Path(path).parent
        for floor in project.floors:
            if floor.background_image:
                candidate = project_dir / floor.background_image
                floor.background_image = (
                    str(candidate) if candidate.exists() else None
                )
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
            QMessageBox.critical(
                self, "Fehler",
                f"Projekt konnte nicht gespeichert werden:\n{exc}",
            )
            return

        self._undo_stack.setClean()
        self._update_title()

    def _confirm_discard(self) -> bool:
        if self._project is None or self._undo_stack.isClean():
            return True
        resp = QMessageBox.question(
            self,
            "Ungespeicherte Änderungen",
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
    # Title
    # ------------------------------------------------------------------

    def _update_title(self) -> None:
        name  = self._project.name if self._project else "Unbenannt"
        dirty = self._project is not None and not self._undo_stack.isClean()
        prefix = "* " if dirty else ""
        self.setWindowTitle(f"{prefix}WiFi Heatmap — {name}")

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # View toggles
    # ------------------------------------------------------------------

    def _toggle_side_view(self, checked: bool) -> None:
        pass

    def _toggle_heatmap(self, checked: bool) -> None:
        pass

    def _toggle_grid(self, checked: bool) -> None:
        self._canvas_widget.set_show_grid(checked)

    def _export(self, fmt: str) -> None:
        pass
