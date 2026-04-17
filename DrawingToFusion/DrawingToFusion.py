import adsk.core
import adsk.fusion
import traceback

from . import config
from .commands.analyzeDrawing.entry import PaletteCommandCreatedHandler
from .commands.analyzeDrawing import entry as analyzeDrawing

handlers = []
_cmd_def = None


def _get_sketch_panel(ui):
    workspace = ui.workspaces.itemById(config.WORKSPACE_ID)
    tab = workspace.toolbarTabs.itemById(config.TOOLBAR_TAB_ID)
    return tab.toolbarPanels.itemById(config.TOOLBAR_PANEL_ID)


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
