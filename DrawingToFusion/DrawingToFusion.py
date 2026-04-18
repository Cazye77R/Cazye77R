import adsk.core
import adsk.fusion
import traceback

from . import config
from .commands.analyzeDrawing.entry import PaletteCommandCreatedHandler
from .commands.analyzeDrawing import entry as analyzeDrawing

handlers = []
_cmd_def = None


def _get_sketch_panel(ui):
    """
    Gibt das Toolbar-Panel zurück, in das der Add-In Button eingehängt wird.
    Wirft RuntimeError mit sprechender Message wenn Workspace/Tab/Panel fehlt.
    """
    workspace = ui.workspaces.itemById(config.WORKSPACE_ID)
    if not workspace:
        raise RuntimeError(
            f"Workspace '{config.WORKSPACE_ID}' nicht gefunden. "
            "Stelle sicher, dass Fusion 360 im Design-Workspace ist."
        )
    tab = workspace.toolbarTabs.itemById(config.TOOLBAR_TAB_ID)
    if not tab:
        raise RuntimeError(
            f"Toolbar-Tab '{config.TOOLBAR_TAB_ID}' nicht gefunden. "
            f"Prüfe TOOLBAR_TAB_ID in config.py."
        )
    panel = tab.toolbarPanels.itemById(config.TOOLBAR_PANEL_ID)
    if not panel:
        raise RuntimeError(
            f"Toolbar-Panel '{config.TOOLBAR_PANEL_ID}' nicht gefunden. "
            f"Prüfe TOOLBAR_PANEL_ID in config.py."
        )
    return panel


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        global _cmd_def

        # Guard against dirty state if the add-in crashed previously
        existing = ui.commandDefinitions.itemById(config.CMD_ANALYZE_ID)
        if existing:
            existing.deleteMe()

        _cmd_def = ui.commandDefinitions.addButtonDefinition(
            config.CMD_ANALYZE_ID,
            config.CMD_ANALYZE_NAME,
            config.CMD_ANALYZE_TOOLTIP,
        )

        on_created = PaletteCommandCreatedHandler(ui)
        _cmd_def.commandCreated.add(on_created)
        handlers.append(on_created)

        panel = _get_sketch_panel(ui)
        ctrl = panel.controls.addCommand(_cmd_def)
        ctrl.isPromotedByDefault = False

    except Exception:
        if ui:
            ui.messageBox(
                f"DrawingToFusion konnte nicht gestartet werden:\n{traceback.format_exc()}"
            )


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        # entry.stop() deletes the palette and clears HTML handlers
        analyzeDrawing.stop()

        panel = _get_sketch_panel(ui)
        ctrl = panel.controls.itemById(config.CMD_ANALYZE_ID)
        if ctrl:
            ctrl.deleteMe()

        cmd_def = ui.commandDefinitions.itemById(config.CMD_ANALYZE_ID)
        if cmd_def:
            cmd_def.deleteMe()

        handlers.clear()

    except Exception:
        if ui:
            ui.messageBox(
                f"DrawingToFusion konnte nicht gestoppt werden:\n{traceback.format_exc()}"
            )
