from __future__ import annotations

import copy
import json
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QGraphicsScene

from models.floor import Floor
from models.measurement import Measurement
from models.project import Project
from utils.colors import dbm_to_color


_LEGEND_H = 64   # legend strip height in pixels at 1× scale


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _qimage_to_bytes(img: QImage) -> bytes:
    """Encode *img* as PNG into an in-memory bytes object (no temp files)."""
    arr = QByteArray()
    buf = QBuffer(arr)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(arr)


def _render_scene(
    scene: QGraphicsScene,
    source_rect: QRectF,
    width: int,
    height: int,
) -> QImage:
    """Render *source_rect* of *scene* into a *width* × *height* QImage."""
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(QColor("#1e1e2e"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(p, QRectF(0, 0, width, height), source_rect)
    p.end()
    return img


def _draw_legend(
    p: QPainter,
    x: int,
    y: int,
    w: int,
    h: int,
    floor: Floor,
    min_dbm: float,
    max_dbm: float,
) -> None:
    """Paint a legend strip: gradient bar + dBm ticks + floor metadata."""
    p.fillRect(x, y, w, h, QColor(0x18, 0x18, 0x28))

    pad = max(8, h // 8)
    bar_x  = x + pad
    bar_y  = y + pad
    bar_w  = min(240, w // 3)
    bar_h  = h - pad * 2 - 14   # leave room for tick labels

    # Horizontal gradient: red (min) → green (max)
    grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
    for i in range(21):
        t = i / 20
        grad.setColorAt(t, dbm_to_color(
            min_dbm + t * (max_dbm - min_dbm), min_dbm, max_dbm
        ))
    p.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), grad)
    p.setPen(QPen(QColor(50, 50, 70), 1))
    p.drawRect(QRectF(bar_x, bar_y, bar_w, bar_h))

    # Tick labels below bar
    fnt7 = QFont()
    fnt7.setPointSize(7)
    p.setFont(fnt7)
    p.setPen(QColor(0x90, 0x90, 0xb0))
    fm7 = QFontMetrics(fnt7)
    for tick in range(5):
        t     = tick / 4
        val   = min_dbm + t * (max_dbm - min_dbm)
        tx    = int(bar_x + t * bar_w)
        label = f"{val:.0f}"
        p.drawText(tx - fm7.horizontalAdvance(label) // 2, y + h - 3, label)
    p.drawText(int(bar_x + bar_w) + 4, y + h - 3, "dBm")

    # Right side metadata
    info_x = bar_x + bar_w + 28
    ssids  = sorted({m.ssid for m in floor.measurements if m.ssid})

    fnt10 = QFont()
    fnt10.setPointSize(9)
    fnt10.setBold(True)
    p.setFont(fnt10)
    p.setPen(QColor(0xb0, 0xb8, 0xd0))
    p.drawText(info_x, y + 18, f"Etage: {floor.name}")

    fnt8 = QFont()
    fnt8.setPointSize(8)
    p.setFont(fnt8)
    p.setPen(QColor(0x80, 0x80, 0xa0))
    line_y = y + 34
    if ssids:
        s = ", ".join(ssids[:3]) + ("…" if len(ssids) > 3 else "")
        p.drawText(info_x, line_y, f"SSID: {s}")
        line_y += 14
    p.drawText(info_x, line_y,
               f"Exportiert: {datetime.now().strftime('%d.%m.%Y  %H:%M')}")


# ── Exporter ──────────────────────────────────────────────────────────────────

class ProjectExporter:

    # ── JSON ─────────────────────────────────────────────────────────

    @staticmethod
    def export_json(project: Project, path: str | Path) -> None:
        """Save project as JSON and copy background images to images/ subfolder."""
        path = Path(path)
        images_dir = path.parent / "images"
        images_dir.mkdir(exist_ok=True)

        data = copy.deepcopy(project.to_dict())
        data["modified_at"] = datetime.now().isoformat()

        for floor_data in data.get("floors", []):
            bg = floor_data.get("background_image")
            if bg:
                src = Path(bg)
                if src.is_absolute() and src.exists():
                    dst = images_dir / src.name
                    if src.resolve() != dst.resolve():
                        shutil.copy2(str(src), str(dst))
                    floor_data["background_image"] = f"images/{src.name}"

        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── PNG ──────────────────────────────────────────────────────────

    @staticmethod
    def render_floor_image(
        scene: QGraphicsScene,
        source_rect: QRectF,
        floor: Floor,
        min_dbm: float,
        max_dbm: float,
        scale: int = 1,
    ) -> QImage:
        """Render *scene* at *scale*× resolution with a legend strip appended."""
        scale   = max(1, min(4, scale))
        base_w  = max(int(source_rect.width()),  200)
        base_h  = max(int(source_rect.height()), 150)
        out_w   = base_w * scale
        out_h   = base_h * scale
        leg_h   = _LEGEND_H * scale

        scene_img = _render_scene(scene, source_rect, out_w, out_h)

        full = QImage(out_w, out_h + leg_h, QImage.Format.Format_RGB32)
        full.fill(QColor("#1e1e2e"))
        p = QPainter(full)
        p.drawImage(0, 0, scene_img)
        _draw_legend(p, 0, out_h, out_w, leg_h, floor, min_dbm, max_dbm)
        p.end()

        return full

    @staticmethod
    def export_png(
        scene: QGraphicsScene,
        source_rect: QRectF,
        floor: Floor,
        path: str | Path,
        min_dbm: float,
        max_dbm: float,
        scale: int = 1,
    ) -> None:
        """Render and save a PNG."""
        img = ProjectExporter.render_floor_image(
            scene, source_rect, floor, min_dbm, max_dbm, scale
        )
        if not img.save(str(path)):
            raise OSError(f"PNG konnte nicht gespeichert werden: {path}")

    # ── PDF ──────────────────────────────────────────────────────────

    @staticmethod
    def export_pdf(
        project: Project,
        floor_images: list[tuple[Floor, QImage]],
        path: str | Path,
        min_dbm: float,
        max_dbm: float,
        critical_threshold: float = -75.0,
        side_view_image: Optional[QImage] = None,
    ) -> None:
        """Build a multi-page PDF report using reportlab (landscape A4)."""
        try:
            from reportlab.lib import colors as rl_colors
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.platypus import (
                HRFlowable,
                Image as RLImage,
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as exc:
            raise ImportError(
                "reportlab ist nicht installiert. "
                "Installieren Sie es mit: pip install reportlab"
            ) from exc

        land_w, land_h = landscape(A4)
        margin   = 18 * mm
        date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        avail_w = land_w - 2 * margin
        avail_h = land_h - 2 * margin - 18 * mm   # leave space for footer

        # ── Statistics ────────────────────────────────────────────────
        all_ms: list[tuple[Floor, Measurement]] = [
            (f, m) for f in project.floors for m in f.measurements
        ]
        total   = len(all_ms)
        best    = max(all_ms, key=lambda x: x[1].dbm, default=None)
        worst   = min(all_ms, key=lambda x: x[1].dbm, default=None)
        avg     = sum(m.dbm for _, m in all_ms) / total if total else 0.0
        n_crit  = sum(1 for _, m in all_ms if m.dbm < critical_threshold)

        # ── QImage → reportlab Image ──────────────────────────────────
        def _rl_img(qimg: QImage, max_w: float, max_h: float) -> RLImage:
            png = _qimage_to_bytes(qimg)
            buf = BytesIO(png)
            asp = qimg.width() / max(qimg.height(), 1)
            if asp > max_w / max_h:
                w, h = max_w, max_w / asp
            else:
                w, h = max_h * asp, max_h
            return RLImage(buf, width=w, height=h)

        # ── Styles ────────────────────────────────────────────────────
        base    = getSampleStyleSheet()

        CYN  = rl_colors.HexColor("#4fc3f7")
        LGRY = rl_colors.HexColor("#b0b8d0")
        GRAY = rl_colors.HexColor("#9090a0")
        TXT  = rl_colors.HexColor("#e0e0e0")
        BG0  = rl_colors.HexColor("#1a1a2a")
        BG1  = rl_colors.HexColor("#2a2a3a")
        BG2  = rl_colors.HexColor("#222232")

        def _ps(name: str, parent: str = "Normal", **kw) -> ParagraphStyle:
            return ParagraphStyle(name, parent=base[parent], **kw)

        title_s = _ps("wh_title",  "Title",   fontSize=24, textColor=CYN,  spaceAfter=6)
        h1_s    = _ps("wh_h1",    "Heading1", fontSize=16, textColor=CYN,  spaceAfter=5)
        h2_s    = _ps("wh_h2",    "Heading2", fontSize=11, textColor=LGRY, spaceAfter=3)
        body_s  = _ps("wh_body",  "Normal",   fontSize=10, textColor=TXT,  spaceAfter=2)
        small_s = _ps("wh_small", "Normal",   fontSize=9,  textColor=GRAY, spaceAfter=2)

        # Reusable cell styles (avoids per-row object creation)
        def _p(text: str, style: ParagraphStyle) -> Paragraph:
            return Paragraph(str(text), style)

        hdr_s  = _ps("wh_th", "Normal", fontSize=8, textColor=CYN,
                     fontName="Helvetica-Bold")
        cell_s = _ps("wh_td", "Normal", fontSize=8, textColor=TXT)
        dim_s  = _ps("wh_td_dim", "Normal", fontSize=8, textColor=GRAY)
        lbl_s  = _ps("wh_lbl", "Normal", fontSize=10, textColor=CYN)
        val_s  = _ps("wh_val", "Normal", fontSize=10, textColor=TXT)

        # ── Footer canvas ─────────────────────────────────────────────
        class _Footer(rl_canvas.Canvas):
            def __init__(self, *args, **kwargs):
                rl_canvas.Canvas.__init__(self, *args, **kwargs)
                self._page_states: list[dict] = []

            def showPage(self) -> None:           # type: ignore[override]
                self._page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self) -> None:              # type: ignore[override]
                n = len(self._page_states)
                pw = self._pagesize[0]
                for state in self._page_states:
                    self.__dict__.update(state)
                    self.setFont("Helvetica", 7)
                    self.setFillColorRGB(0.40, 0.40, 0.50)
                    self.drawCentredString(
                        pw / 2, 9 * mm,
                        f"WiFi Heatmap Tool  —  {date_str}  —  "
                        f"Seite {self._pageNumber}/{n}",
                    )
                    self.setStrokeColorRGB(0.25, 0.25, 0.35)
                    self.setLineWidth(0.5)
                    self.line(margin, 15 * mm, pw - margin, 15 * mm)
                    rl_canvas.Canvas.showPage(self)
                rl_canvas.Canvas.save(self)

        # ── Story ─────────────────────────────────────────────────────
        story: list = []

        # === Title page ===
        story.append(Spacer(1, 28 * mm))
        story.append(Paragraph("WiFi Heatmap Bericht", title_s))
        story.append(Paragraph(f"Projekt: {project.name}", h1_s))
        story.append(Paragraph(f"Erstellt: {date_str}", small_s))
        story.append(Spacer(1, 10 * mm))
        story.append(HRFlowable(
            width="100%", thickness=0.5,
            color=rl_colors.HexColor("#3a3a4a"),
        ))
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Zusammenfassung", h1_s))
        story.append(Spacer(1, 3 * mm))

        def _sum_row(label: str, value: str) -> list:
            return [_p(label, lbl_s), _p(value, val_s)]

        sum_rows = [
            _sum_row("Etagen:", str(len(project.floors))),
            _sum_row("Messpunkte gesamt:", str(total)),
        ]
        if best:
            fl, m = best
            sum_rows.append(_sum_row(
                "Stärkstes Signal:",
                f"{m.dbm:+.1f} dBm  ·  ({m.x:.0f}, {m.y:.0f})  ·  {fl.name}",
            ))
        if worst:
            fl, m = worst
            sum_rows.append(_sum_row(
                "Schwächstes Signal:",
                f"{m.dbm:+.1f} dBm  ·  ({m.x:.0f}, {m.y:.0f})  ·  {fl.name}",
            ))
        if total:
            sum_rows.append(_sum_row("Ø Signal:", f"{avg:+.1f} dBm"))
        sum_rows.append(_sum_row(
            f"Kritische Zonen (< {critical_threshold:.0f} dBm):",
            str(n_crit),
        ))

        col_w = avail_w * 0.40
        sum_tbl = Table(sum_rows, colWidths=[col_w, avail_w - col_w])
        sum_tbl.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG1, BG2]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(sum_tbl)
        story.append(PageBreak())

        # === Floor pages ===
        for floor, qimg in floor_images:
            story.append(Paragraph(
                f"Etage: {floor.name} "
                f"<font color='#606070' size='10'>(Level {floor.level})</font>",
                h1_s,
            ))
            story.append(Spacer(1, 2 * mm))

            if qimg is not None and not qimg.isNull():
                story.append(_rl_img(qimg, avail_w, avail_h * 0.54))
                story.append(Spacer(1, 3 * mm))

            if floor.measurements:
                story.append(Paragraph("Messpunkte", h2_s))
                hdr_row = [
                    _p(c, hdr_s)
                    for c in ["Nr.", "dBm", "SSID", "Channel", "Band", "Zeitpunkt"]
                ]
                rows = [hdr_row]
                for i, m in enumerate(floor.measurements, 1):
                    rows.append([
                        _p(str(i),                           cell_s),
                        _p(f"{m.dbm:+.1f}",                 cell_s),
                        _p(m.ssid or "—",                   cell_s),
                        _p(str(m.channel),                  cell_s),
                        _p(m.band,                          cell_s),
                        _p(m.timestamp.strftime("%d.%m.%Y %H:%M"), dim_s),
                    ])

                fracs = [0.06, 0.09, 0.34, 0.11, 0.13, 0.27]
                col_ws = [avail_w * f for f in fracs]
                m_tbl = Table(rows, colWidths=col_ws, repeatRows=1)
                m_tbl.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1,  0), BG0),
                    ("ROWBACKGROUNDS",(0, 1), (-1, -1), [BG1, BG2]),
                    ("TOPPADDING",    (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                    ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID",          (0, 0), (-1, -1), 0.3,
                     rl_colors.HexColor("#3a3a4a")),
                ]))
                story.append(m_tbl)
            else:
                story.append(Paragraph(
                    "Keine Messpunkte auf dieser Etage.", small_s
                ))

            story.append(PageBreak())

        # === Side view page (>1 floor) ===
        if (len(project.floors) > 1
                and side_view_image is not None
                and not side_view_image.isNull()):
            story.append(Paragraph("Seitenansicht — Gesamtgebäude", h1_s))
            story.append(Spacer(1, 3 * mm))
            story.append(_rl_img(side_view_image, avail_w, avail_h * 0.84))
            story.append(PageBreak())

        # Drop trailing PageBreak(s)
        while story and isinstance(story[-1], PageBreak):
            story.pop()

        # ── Build document ────────────────────────────────────────────
        doc = SimpleDocTemplate(
            str(path),
            pagesize=landscape(A4),
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=18 * mm,
        )
        doc.build(story, canvasmaker=_Footer)
