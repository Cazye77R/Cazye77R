"""Single-owner camera hub shared by every Streamlit page in the process.

A webcam is a machine-wide resource, but ``st.session_state`` is scoped per
browser session — so coordinating there would still let two pages (or two
tabs) open ``/dev/video0`` at the same time. On Linux the second open
typically succeeds but never streams, leaving one page with a permanently
frozen image. This module therefore keeps the capture in a *module-global*
singleton, which is the same scope as the device itself.

One worker thread owns the only ``VideoCapture`` and the only MediaPipe graph.
Pages call :func:`acquire` to become the current owner; the previous owner
simply stops being called. Nothing is reopened on page navigation, so there is
no black frame and no ~1 s MediaPipe rebuild when switching pages.

Processors run **on the worker thread**: they may only touch plain dicts and
queues, and must never call ``st.*``.

IMPORTANT: cv2 / mediapipe are imported lazily inside functions so this module
stays importable on a headless machine (the test suite relies on that).
"""

import threading
import time
from dataclasses import dataclass

import config

# Release the camera when no page has polled for this long (tab closed).
_IDLE_TIMEOUT_SEC = 60.0
# Give up and report an error after this many consecutive failed reads.
_MAX_READ_FAILURES = 60


class CameraError(RuntimeError):
    """Raised when the camera cannot be opened or does not deliver frames."""


def open_capture(index: int | None = None, width: int | None = None,
                 height: int | None = None):
    """Open and *probe* a camera, raising CameraError with a readable message.

    Probing matters: a device can open successfully and still never stream
    (typically because another process already holds it), which would
    otherwise show up as an app that silently does nothing.
    """
    import cv2

    index = config.CAM_INDEX if index is None else index
    width = config.CAM_W if width is None else width
    height = config.CAM_H if height is None else height

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        raise CameraError(
            f"Kamera {index} konnte nicht geöffnet werden.\n"
            "Ist eine Webcam angeschlossen? Mit --camera N lässt sich ein "
            "anderer Index wählen."
        )
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    ok, _ = cap.read()
    if not ok:
        cap.release()
        raise CameraError(
            f"Kamera {index} liefert keine Bilder.\n"
            "Wird sie gerade von einem anderen Programm benutzt "
            "(Videokonferenz, zweite Instanz dieser App)?"
        )
    return cap


@dataclass
class Status:
    running: bool
    owner: str | None
    error: str | None
    fps: int


class _Hub:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._owner: str | None = None
        self._processor = None
        self._payload: tuple[str, dict] | None = None
        self._error: str | None = None
        self._fps = 0
        self._last_poll = 0.0

    # ── Public API ────────────────────────────────────────────────────────

    def acquire(self, owner: str, processor) -> None:
        """Make ``owner`` the active consumer. Last acquirer wins.

        Idempotent for the current owner, so calling it on every Streamlit
        rerun is cheap.
        """
        with self._lock:
            self._owner = owner
            self._processor = processor
            self._last_poll = time.time()
            if self._thread is None or not self._thread.is_alive():
                self._error = None
                self._stop.clear()
                self._thread = threading.Thread(
                    target=self._run, name="handcursor-camera", daemon=True)
                self._thread.start()

    def latest(self, owner: str) -> dict | None:
        """Newest payload produced *for this owner*, or None."""
        with self._lock:
            self._last_poll = time.time()
            if self._payload is None or self._owner != owner:
                return None
            payload_owner, payload = self._payload
            return payload if payload_owner == owner else None

    def owns(self, owner: str) -> bool:
        with self._lock:
            return self._owner == owner

    def status(self) -> Status:
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            return Status(running=running, owner=self._owner,
                          error=self._error, fps=self._fps)

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the worker and release the camera."""
        with self._lock:
            thread = self._thread
        self._stop.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            self._thread = None
            self._owner = None
            self._processor = None
            self._payload = None
            self._fps = 0

    # ── Worker ────────────────────────────────────────────────────────────

    def _run(self) -> None:
        import cv2
        import mediapipe as mp

        try:
            cap = open_capture()
        except CameraError as exc:
            with self._lock:
                self._error = str(exc)
            return
        except Exception as exc:                      # pragma: no cover
            with self._lock:
                self._error = f"Kamera-Fehler: {exc}"
            return

        mp_hands = mp.solutions.hands
        failures = 0
        fps_times: list[float] = []

        try:
            with mp_hands.Hands(
                max_num_hands=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7,
            ) as hands:
                while not self._stop.is_set():
                    ok, frame = cap.read()
                    if not ok:
                        failures += 1
                        if failures >= _MAX_READ_FAILURES:
                            with self._lock:
                                self._error = (
                                    "Die Kamera hat die Bildübertragung beendet. "
                                    "Wurde sie abgezogen oder von einem anderen "
                                    "Programm übernommen?")
                            break
                        time.sleep(0.01)
                        continue
                    failures = 0

                    now = time.time()
                    fps_times = [t for t in fps_times if now - t < 1.0]
                    fps_times.append(now)

                    frame = cv2.flip(frame, 1)
                    result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                    with self._lock:
                        owner, processor = self._owner, self._processor
                        self._fps = len(fps_times)
                        idle = now - self._last_poll

                    # Nobody has rendered for a while — the tab is gone.
                    if idle > _IDLE_TIMEOUT_SEC:
                        break

                    if processor is None:
                        time.sleep(0.01)
                        continue

                    try:
                        payload = processor(frame, result)
                    except Exception as exc:          # pragma: no cover
                        with self._lock:
                            self._error = f"Fehler in der Bildverarbeitung: {exc}"
                        break

                    if payload is not None:
                        payload.setdefault("fps", len(fps_times))
                        with self._lock:
                            if self._owner == owner:
                                self._payload = (owner, payload)
        finally:
            cap.release()


HUB = _Hub()


def acquire(owner: str, processor) -> None:
    HUB.acquire(owner, processor)


def latest(owner: str) -> dict | None:
    return HUB.latest(owner)


def status() -> Status:
    return HUB.status()


def stop() -> None:
    HUB.stop()
