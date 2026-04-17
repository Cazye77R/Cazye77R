import adsk.core
import adsk.fusion
import os
import traceback

from ... import config
from ...core.vision_analyzer import VisionAnalyzer
from ...core.geometry_builder import GeometryBuilder

ui = None
cmd_def = None
handlers = []


class AnalyzeDrawingCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False

            on_execute = AnalyzeDrawingCommandExecuteHandler()
            cmd.execute.add(on_execute)
            handlers.append(on_execute)

            inputs = cmd.commandInputs

            inputs.addStringValueInput(
                "imagePath",
                "Bildpfad",
                "",
            )
            inputs.addBoolValueInput(
                "autoModel",
                "Modell automatisch erstellen",
                True,
                "",
                True,
            )

        except Exception:
            if ui:
                ui.messageBox(f"Command created failed:\n{traceback.format_exc()}")


class AnalyzeDrawingCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            image_path = inputs.itemById("imagePath").value
            auto_model = inputs.itemById("autoModel").value

            if not image_path or not os.path.isfile(image_path):
                ui.messageBox("Bitte einen gültigen Bildpfad angeben.")
                return

            analyzer = VisionAnalyzer()
            drawing_data = analyzer.analyze(image_path)

            if auto_model and drawing_data:
                builder = GeometryBuilder()
                builder.build(drawing_data)

        except Exception:
            if ui:
                ui.messageBox(f"Execute failed:\n{traceback.format_exc()}")


def start():
    global ui, cmd_def

    app = adsk.core.Application.get()
    ui = app.userInterface

    cmd_def = ui.commandDefinitions.addButtonDefinition(
        config.CMD_ANALYZE_ID,
        config.CMD_ANALYZE_NAME,
        config.CMD_ANALYZE_TOOLTIP,
    )

    on_created = AnalyzeDrawingCommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    handlers.append(on_created)

    panel = ui.allToolbarPanels.itemById(config.CMD_ANALYZE_PANEL)
    if panel:
        panel.controls.addCommand(cmd_def)


def stop():
    panel = None
    try:
        app = adsk.core.Application.get()
        ui_local = app.userInterface

        panel = ui_local.allToolbarPanels.itemById(config.CMD_ANALYZE_PANEL)
        if panel:
            ctrl = panel.controls.itemById(config.CMD_ANALYZE_ID)
            if ctrl:
                ctrl.deleteMe()

        if cmd_def:
            cmd_def.deleteMe()

    except Exception:
        pass
