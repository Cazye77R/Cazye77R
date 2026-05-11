from __future__ import annotations

import copy
from typing import Any, Callable, Optional

from PySide6.QtGui import QUndoCommand

from models.floor import Floor
from models.measurement import Measurement


class _Cmd(QUndoCommand):
    """
    Base for all canvas commands.

    The "first-redo skip" pattern lets callers apply the operation themselves
    (fast path, already visible in the scene) and then push the command onto
    the stack.  push() calls redo() immediately, but we skip that first call
    so the effect is not applied twice.  All subsequent redo() calls go
    through _do_redo(), and undo() always goes through _do_undo().
    """

    def __init__(self, text: str, refresh: Callable[[], None]) -> None:
        super().__init__(text)
        self._refresh = refresh
        self._first = True

    def redo(self) -> None:
        if self._first:
            self._first = False
            return
        self._do_redo()
        self._refresh()

    def undo(self) -> None:
        self._do_undo()
        self._refresh()

    def _do_redo(self) -> None:
        raise NotImplementedError

    def _do_undo(self) -> None:
        raise NotImplementedError


# ── Element commands ──────────────────────────────────────────────────────────

class AddElementCommand(_Cmd):
    def __init__(
        self, floor: Floor, elem: dict[str, Any], refresh: Callable[[], None]
    ) -> None:
        super().__init__(f"Hinzufügen ({elem.get('type', 'element')})", refresh)
        self._floor = floor
        self._elem  = copy.deepcopy(elem)

    def _do_redo(self) -> None:
        self._floor.elements.append(copy.deepcopy(self._elem))

    def _do_undo(self) -> None:
        eid = self._elem["id"]
        self._floor.elements = [e for e in self._floor.elements if e.get("id") != eid]


class RemoveElementCommand(_Cmd):
    def __init__(
        self, floor: Floor, elem: dict[str, Any], refresh: Callable[[], None]
    ) -> None:
        super().__init__(f"Löschen ({elem.get('type', 'element')})", refresh)
        self._floor = floor
        self._elem  = copy.deepcopy(elem)

    def _do_redo(self) -> None:
        eid = self._elem["id"]
        self._floor.elements = [e for e in self._floor.elements if e.get("id") != eid]

    def _do_undo(self) -> None:
        self._floor.elements.append(copy.deepcopy(self._elem))


class MoveElementCommand(_Cmd):
    def __init__(
        self,
        floor: Floor,
        elem_id: str,
        old_pos: dict[str, float],
        new_pos: dict[str, float],
        refresh: Callable[[], None],
    ) -> None:
        super().__init__("Verschieben", refresh)
        self._floor = floor
        self._id    = elem_id
        self._old   = old_pos.copy()
        self._new   = new_pos.copy()

    def _apply(self, pos: dict[str, float]) -> None:
        for e in self._floor.elements:
            if e.get("id") == self._id:
                e.update(pos)
                return

    def _do_redo(self) -> None:
        self._apply(self._new)

    def _do_undo(self) -> None:
        self._apply(self._old)


# ── Measurement commands ──────────────────────────────────────────────────────

class AddMeasurementCommand(_Cmd):
    def __init__(
        self, floor: Floor, m: Measurement, refresh: Callable[[], None]
    ) -> None:
        super().__init__("Messpunkt hinzufügen", refresh)
        self._floor = floor
        self._m     = m

    def _do_redo(self) -> None:
        if self._m not in self._floor.measurements:
            self._floor.measurements.append(self._m)

    def _do_undo(self) -> None:
        self._floor.measurements = [
            x for x in self._floor.measurements if x is not self._m
        ]


class RemoveMeasurementCommand(_Cmd):
    def __init__(
        self, floor: Floor, m: Measurement, refresh: Callable[[], None]
    ) -> None:
        super().__init__("Messpunkt löschen", refresh)
        self._floor = floor
        self._m     = m

    def _do_redo(self) -> None:
        self._floor.measurements = [
            x for x in self._floor.measurements if x is not self._m
        ]

    def _do_undo(self) -> None:
        if self._m not in self._floor.measurements:
            self._floor.measurements.append(self._m)


# ── Background / router commands ──────────────────────────────────────────────

# bg_state = (path: Optional[str], offset: tuple[float,float], scale: float)
_BgState = tuple[Optional[str], tuple[float, float], float]


class SetBackgroundCommand(_Cmd):
    def __init__(
        self,
        floor: Floor,
        old_state: _BgState,
        new_state: _BgState,
        refresh: Callable[[], None],
    ) -> None:
        super().__init__("Hintergrundbild ändern", refresh)
        self._floor = floor
        self._old   = old_state
        self._new   = new_state

    def _apply(self, state: _BgState) -> None:
        self._floor.background_image, self._floor.bg_offset, self._floor.bg_scale = state

    def _do_redo(self) -> None:
        self._apply(self._new)

    def _do_undo(self) -> None:
        self._apply(self._old)


class SetRouterCommand(_Cmd):
    def __init__(
        self,
        floor: Floor,
        old_pos: Optional[tuple[float, float]],
        new_pos: Optional[tuple[float, float]],
        refresh: Callable[[], None],
    ) -> None:
        super().__init__("Router setzen", refresh)
        self._floor = floor
        self._old   = old_pos
        self._new   = new_pos

    def _do_redo(self) -> None:
        self._floor.router_position = self._new

    def _do_undo(self) -> None:
        self._floor.router_position = self._old
