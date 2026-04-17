import adsk.core
import adsk.fusion
import traceback

from .commands.analyzeDrawing import entry as analyzeDrawing

commands = [analyzeDrawing]
handlers = []


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        for cmd in commands:
            cmd.start()

    except Exception:
        if ui:
            ui.messageBox(f"DrawingToFusion start failed:\n{traceback.format_exc()}")


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        for cmd in commands:
            cmd.stop()

    except Exception:
        if ui:
            ui.messageBox(f"DrawingToFusion stop failed:\n{traceback.format_exc()}")
