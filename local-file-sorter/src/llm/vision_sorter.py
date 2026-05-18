"""Build a SortPlan from vision-based image classifications."""
from __future__ import annotations

import re
from pathlib import Path

from src.llm.schemas import OpType, SortAction, SortPlan


def _sanitize_folder_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", "_", name)
    name = name[:64]
    return name or "Sonstiges"


def build_vision_plan(
    image_classifications: dict[Path, str],
    target_folder: Path,
) -> SortPlan:
    """Convert {image_path: category} mapping into a SortPlan."""
    categories: dict[str, Path] = {}   # sanitized name → subfolder Path
    actions: list[SortAction] = []

    for img_path, raw_category in image_classifications.items():
        folder_name = _sanitize_folder_name(raw_category)
        if folder_name not in categories:
            subfolder = target_folder / folder_name
            categories[folder_name] = subfolder
            actions.append(SortAction(
                op_type=OpType.create_folder,
                source=None,
                destination=subfolder,
                reason=f"Kategorie: {raw_category}",
            ))
        dest_folder = categories[folder_name]
        actions.append(SortAction(
            op_type=OpType.move,
            source=img_path,
            destination=dest_folder / img_path.name,
            reason=f"Vision: {raw_category}",
        ))

    n_img  = len(image_classifications)
    n_cats = len(categories)
    summary = (
        f"Vision-Sortierung: {n_img} Bild{'er' if n_img != 1 else ''} "
        f"in {n_cats} Kategorie{'n' if n_cats != 1 else ''}."
    )
    return SortPlan(actions=actions, summary=summary)
