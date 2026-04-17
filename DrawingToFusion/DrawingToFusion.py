import adsk.core
import adsk.fusion
import os
import traceback

from . import config

handlers = []
_cmd_def = None


class _ButtonCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, ui):
        super().__init__()
        self._ui = ui

    def notify(self, args):
        try:
            _open_palette(self._ui)
        except Exception:
            self._ui.messageBox(
                f"Fehler beim Öffnen der Palette:\n{traceback.format_exc()}"
            )


def _open_palette(ui):
    palette = ui.palettes.itemById(config.PALETTE_ID)
    if palette:
        palette.isVisible = True
        return

    html_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        config.PALETTE_URL,
    )
    ui.palettes.add(
        config.PALETTE_ID,
        config.PALETTE_TITLE,
        html_path,
        True,   # isVisible
        True,   # showCloseButton
        True,   # isResizable
        config.PALETTE_WIDTH,
        config.PALETTE_HEIGHT,
    )


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

        on_created = _ButtonCreatedHandler(ui)
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

        palette = ui.palettes.itemById(config.PALETTE_ID)
        if palette:
            palette.deleteMe()

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
