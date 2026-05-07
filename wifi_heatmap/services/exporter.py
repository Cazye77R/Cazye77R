from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.project import Project


class Exporter:
    def __init__(self, project: "Project") -> None:
        self.project = project

    def export_png(self, path: str | Path) -> None:
        """Render heatmap canvas to PNG. Requires a rendered QPixmap — to be implemented."""
        raise NotImplementedError

    def export_pdf(self, path: str | Path) -> None:
        """Export project as PDF report. Requires reportlab. To be implemented."""
        raise NotImplementedError

    def export_json(self, path: str | Path) -> None:
        self.project.save(path)
