/**
 * Scene.jsx — Isometric SVG main scene
 *
 * Features:
 *  - Ambient light gradient + vignette overlay
 *  - Decorative office plants + window glow
 *  - Camera pan (mouse drag) + zoom toward cursor (scroll wheel)
 *  - forwardRef exposes fitScreen() and screenshot() to parent
 *  - Static items memoized; React.memo on furniture avoids per-frame re-renders
 */

import { forwardRef, useImperativeHandle, useRef, useState, useMemo, useEffect } from 'react';
import { iso, sortByDepth, screenToGrid } from '../engine/iso';
import { TILE_W, TILE_H, GRID_COLS, GRID_ROWS } from '../data/constants';
import {
  WALLS, DESKS, MEETING_TABLE, FILING_CABINET, COFFEE_MACHINE,
} from '../data/officeLayout';
import { FurnitureStyles, DeskUnit, CabinetBox, CoffeeMachine, MeetingTable } from './Furniture';
import AgentSprite from './Agent';

const WALL_SET = new Set(WALLS.map(([gx, gy]) => `${gx},${gy}`));

// ---------------------------------------------------------------------------
// FloorTile
// ---------------------------------------------------------------------------

function FloorTile({ gx, gy, hovered, onMouseEnter, onMouseLeave }) {
  const { x, y } = iso(gx, gy);
  const base = (gx + gy) % 2 === 0 ? '#d8c9a8' : '#cbbf98';
  const fill = hovered ? '#e8d8b8' : base;
  return (
    <polygon
      points={`${x},${y - TILE_H / 2} ${x + TILE_W / 2},${y} ${x},${y + TILE_H / 2} ${x - TILE_W / 2},${y}`}
      fill={fill}
      stroke="#b8a880"
      strokeWidth={0.3}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    />
  );
}

// ---------------------------------------------------------------------------
// WallBox  (slightly richer colours)
// ---------------------------------------------------------------------------

const WALL_H = 24;

function WallBox({ gx, gy }) {
  const { x, y } = iso(gx, gy);
  return (
    <g>
      {/* Top face */}
      <polygon
        points={`${x},${y-TILE_H/2-WALL_H} ${x+TILE_W/2},${y-WALL_H} ${x},${y+TILE_H/2-WALL_H} ${x-TILE_W/2},${y-WALL_H}`}
        fill="#6e8290" stroke="#4e6270" strokeWidth={0.4}
      />
      {/* Right face */}
      <polygon
        points={`${x+TILE_W/2},${y-WALL_H} ${x},${y+TILE_H/2-WALL_H} ${x},${y+TILE_H/2} ${x+TILE_W/2},${y}`}
        fill="#4e6270" stroke="#3e5260" strokeWidth={0.4}
      />
      {/* Left face */}
      <polygon
        points={`${x-TILE_W/2},${y-WALL_H} ${x},${y+TILE_H/2-WALL_H} ${x},${y+TILE_H/2} ${x-TILE_W/2},${y}`}
        fill="#5e7280" stroke="#3e5260" strokeWidth={0.4}
      />
      {/* Baseboard line */}
      <line x1={x-TILE_W/2} y1={y} x2={x} y2={y+TILE_H/2} stroke="#3e5260" strokeWidth={0.8} />
      <line x1={x+TILE_W/2} y1={y} x2={x} y2={y+TILE_H/2} stroke="#3e5260" strokeWidth={0.8} />
    </g>
  );
}

// ---------------------------------------------------------------------------
// WindowWall — WallBox with a glowing window panel
// ---------------------------------------------------------------------------

function WindowWall({ gx, gy }) {
  const { x, y } = iso(gx, gy);
  const ty = y - TILE_H / 2 - WALL_H;

  return (
    <g>
      <WallBox gx={gx} gy={gy} />

      {/* Window frame on left face */}
      <rect x={x - TILE_W * 0.32} y={ty + 4} width={TILE_W * 0.55} height={WALL_H * 0.6}
            rx={1.5} fill="#b3e5fc" opacity={0.82} />
      {/* Cross bars */}
      <line x1={x - TILE_W * 0.32 + TILE_W * 0.275} y1={ty + 4}
            x2={x - TILE_W * 0.32 + TILE_W * 0.275} y2={ty + 4 + WALL_H * 0.6}
            stroke="#7ec8e3" strokeWidth={0.8} opacity={0.7} />
      <line x1={x - TILE_W * 0.32} y1={ty + 4 + WALL_H * 0.3}
            x2={x - TILE_W * 0.32 + TILE_W * 0.55} y2={ty + 4 + WALL_H * 0.3}
            stroke="#7ec8e3" strokeWidth={0.8} opacity={0.7} />

      {/* Light spill on floor */}
      <ellipse cx={x - TILE_W * 0.15} cy={y + TILE_H * 0.3}
               rx={TILE_W * 0.55} ry={TILE_H * 0.5}
               fill="#b3e5fc" opacity={0.09} />
    </g>
  );
}

// ---------------------------------------------------------------------------
// Plant  — decorative isometric pot plant
// ---------------------------------------------------------------------------

function Plant({ gx, gy }) {
  const { x, y } = iso(gx, gy, 0);
  return (
    <g transform={`translate(${x}, ${y})`}>
      {/* Shadow */}
      <ellipse cx={0} cy={2} rx={10} ry={4} fill="rgba(0,0,0,0.15)" />
      {/* Pot */}
      <polygon points="-7,0 7,0 5,11 -5,11" fill="#b54a20" />
      <polygon points="7,0 10,-2 8,9 5,11"   fill="#9a3e1a" />
      <ellipse cx={0} cy={0} rx={7} ry={3} fill="#c8592a" />
      {/* Soil */}
      <ellipse cx={0} cy={0} rx={6} ry={2.5} fill="#5d3a1a" />
      {/* Stems */}
      <line x1={0}  y1={0} x2={-5}  y2={-15} stroke="#2e7d32" strokeWidth={1.5} />
      <line x1={0}  y1={-5} x2={4}  y2={-18} stroke="#388e3c" strokeWidth={1.5} />
      <line x1={-1} y1={-8} x2={2}  y2={-20} stroke="#43a047" strokeWidth={1.2} />
      {/* Leaves */}
      <ellipse cx={-8}  cy={-17} rx={7}   ry={4}   fill="#2e7d32" transform="rotate(-35 -8  -17)" />
      <ellipse cx={6}   cy={-20} rx={6}   ry={3.5} fill="#388e3c" transform="rotate(25  6  -20)" />
      <ellipse cx={0}   cy={-22} rx={5.5} ry={3.5} fill="#43a047" />
      <ellipse cx={-4}  cy={-24} rx={4}   ry={2.5} fill="#66bb6a" transform="rotate(-15 -4 -24)" />
    </g>
  );
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------

const DEFAULT_CAMERA = { x: 0, y: 0, zoom: 1 };

const Scene = forwardRef(function Scene({ agents, selectedId, onAgentClick, onTileClick }, ref) {
  const svgRef    = useRef(null);
  const [hovered, setHovered] = useState(null);
  const [camera,  setCamera]  = useState(DEFAULT_CAMERA);

  const cameraRef  = useRef(camera);
  useEffect(() => { cameraRef.current = camera; }, [camera]);

  const isDragging = useRef(false);
  const hasDragged = useRef(false);
  const dragStart  = useRef({ mouseX: 0, mouseY: 0, camX: 0, camY: 0 });

  // ── forwardRef API ────────────────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    fitScreen: () => setCamera(DEFAULT_CAMERA),
    screenshot: () => {
      const svg = svgRef.current;
      if (!svg) return;
      const raw    = new XMLSerializer().serializeToString(svg);
      const svgStr = '<?xml version="1.0" encoding="utf-8"?>' + raw;
      const url    = URL.createObjectURL(new Blob([svgStr], { type: 'image/svg+xml' }));
      const img    = new Image();
      img.onload = () => {
        const canvas = Object.assign(document.createElement('canvas'), { width: 860, height: 520 });
        const ctx    = canvas.getContext('2d');
        ctx.fillStyle = '#0e1525';
        ctx.fillRect(0, 0, 860, 520);
        ctx.drawImage(img, 0, 0);
        canvas.toBlob((b) => {
          const a = Object.assign(document.createElement('a'), {
            href: URL.createObjectURL(b), download: 'agent-office-screenshot.png',
          });
          a.click();
          URL.revokeObjectURL(a.href);
        });
        URL.revokeObjectURL(url);
      };
      img.src = url;
    },
  }));

  // ── Global drag listeners ─────────────────────────────────────────────────
  useEffect(() => {
    function onMove(e) {
      if (!isDragging.current) return;
      const dx = e.clientX - dragStart.current.mouseX;
      const dy = e.clientY - dragStart.current.mouseY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasDragged.current = true;
      if (hasDragged.current)
        setCamera((c) => ({ ...c, x: dragStart.current.camX + dx, y: dragStart.current.camY + dy }));
    }
    function onUp() {
      if (isDragging.current) { isDragging.current = false; document.body.style.cursor = ''; }
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  // ── Scroll-wheel zoom ─────────────────────────────────────────────────────
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    function onWheel(e) {
      e.preventDefault();
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      const rect   = el.getBoundingClientRect();
      const svgW   = el.viewBox.baseVal.width  || 860;
      const svgH   = el.viewBox.baseVal.height || 520;
      const mx     = (e.clientX - rect.left) * (svgW / rect.width);
      const my     = (e.clientY - rect.top)  * (svgH / rect.height);
      setCamera((c) => {
        const newZoom = Math.min(1.8, Math.max(0.5, c.zoom * factor));
        const wx = (mx - c.x) / c.zoom;
        const wy = (my - c.y) / c.zoom;
        return { x: mx - wx * newZoom, y: my - wy * newZoom, zoom: newZoom };
      });
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  // ── Mouse down (start drag) ───────────────────────────────────────────────
  function handleMouseDown(e) {
    if (e.button !== 0) return;
    isDragging.current = true;
    hasDragged.current = false;
    dragStart.current  = {
      mouseX: e.clientX, mouseY: e.clientY,
      camX: cameraRef.current.x, camY: cameraRef.current.y,
    };
    document.body.style.cursor = 'grabbing';
  }

  // ── Click-to-move ─────────────────────────────────────────────────────────
  function handleSvgClick(e) {
    if (hasDragged.current) return;
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const svgPt  = pt.matrixTransform(svg.getScreenCTM().inverse());
    const cam    = cameraRef.current;
    const worldX = (svgPt.x - cam.x) / cam.zoom;
    const worldY = (svgPt.y - cam.y) / cam.zoom;
    const { gx, gy } = screenToGrid(worldX, worldY);
    if (gx >= 0 && gx < GRID_COLS && gy >= 0 && gy < GRID_ROWS) onTileClick?.(gx, gy);
  }

  // ── Derived values ────────────────────────────────────────────────────────
  const cabinetOpen   = agents.some((a) => a.currentState === 'AT_CABINET');
  const meetingActive = agents.some((a) => a.currentState === 'IN_MEETING');

  const deskNameMap = useMemo(() => {
    const m = {};
    agents.forEach((a) => { m[`${a.homePos.gx},${a.homePos.gy}`] = a.name; });
    return m;
  }, [agents]);

  // Static items: computed once
  const staticItems = useMemo(() => {
    const items = [];
    WALLS.forEach(([gx, gy]) => {
      // Windows on specific top-wall tiles
      const isWindow = gy === 0 && (gx === 4 || gx === 6);
      items.push({ gx, gy, gz: 0, type: isWindow ? 'windowwall' : 'wall', key: `w-${gx}-${gy}` });
    });
    DESKS.forEach(([gx, gy])          => items.push({ gx, gy, gz: 0, type: 'desk',    key: `d-${gx}-${gy}` }));
    items.push({ gx: 3, gy: 4, gz: 0, type: 'meeting', key: 'meeting' });
    FILING_CABINET.forEach(([gx, gy]) => items.push({ gx, gy, gz: 0, type: 'cabinet', key: `cab-${gx}-${gy}` }));
    COFFEE_MACHINE.forEach(([gx, gy]) => items.push({ gx, gy, gz: 0, type: 'coffee',  key: `cof-${gx}-${gy}` }));
    // Decorative plants (walkable cells, not in OFFICE_OBSTACLES)
    items.push({ gx: 2, gy: 7, gz: 0, type: 'plant', key: 'plant-sw' });
    items.push({ gx: 7, gy: 3, gz: 0, type: 'plant', key: 'plant-ne' });
    return items;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Per-frame merge + sort
  const sorted = useMemo(() => {
    const agentItems = agents.map((a) => {
      const walking = a.currentState === 'WALKING' && a.path.length > 0 && a.pathIndex < a.path.length;
      const t   = a._stepProgress ?? 0;
      const egx = walking ? a.pos.gx + (a.path[a.pathIndex].gx - a.pos.gx) * t : a.pos.gx;
      const egy = walking ? a.pos.gy + (a.path[a.pathIndex].gy - a.pos.gy) * t : a.pos.gy;
      return { gx: egx, gy: egy, gz: 1, type: 'agent', agent: a, key: `ag-${a.id}` };
    });
    return sortByDepth([...staticItems, ...agentItems]);
  }, [agents, staticItems]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <svg
      ref={svgRef}
      width="100%"
      height="100%"
      viewBox="0 0 860 520"
      preserveAspectRatio="xMidYMid meet"
      style={{
        background: 'var(--scene-bg, #0e1525)',
        display: 'block',
        cursor: selectedId ? 'crosshair' : 'grab',
      }}
      onClick={handleSvgClick}
      onMouseDown={handleMouseDown}
    >
      <FurnitureStyles />

      {/* ── Global defs ── */}
      <defs>
        <radialGradient id="ambientCenter" cx="48%" cy="44%" r="55%">
          <stop offset="0%"   stopColor="#1e3a60" stopOpacity="0.55" />
          <stop offset="55%"  stopColor="#0e1525" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#040810" stopOpacity="0.7" />
        </radialGradient>
        <radialGradient id="ambientLight" cx="48%" cy="44%" r="55%">
          <stop offset="0%"   stopColor="#c8dcff" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#000"    stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* ── Camera group — everything pans/zooms together ── */}
      <g transform={`translate(${camera.x}, ${camera.y}) scale(${camera.zoom})`}>

        {/* Floor tiles */}
        {Array.from({ length: GRID_ROWS }, (_, gy) =>
          Array.from({ length: GRID_COLS }, (_, gx) => {
            if (WALL_SET.has(`${gx},${gy}`)) return null;
            return (
              <FloorTile
                key={`ft-${gx}-${gy}`}
                gx={gx} gy={gy}
                hovered={hovered?.gx === gx && hovered?.gy === gy}
                onMouseEnter={() => setHovered({ gx, gy })}
                onMouseLeave={() => setHovered(null)}
              />
            );
          })
        )}

        {/* Depth-sorted objects */}
        {sorted.map((item) => {
          switch (item.type) {
            case 'wall':
              return <WallBox key={item.key} gx={item.gx} gy={item.gy} />;
            case 'windowwall':
              return <WindowWall key={item.key} gx={item.gx} gy={item.gy} />;
            case 'desk':
              return <DeskUnit key={item.key} gx={item.gx} gy={item.gy}
                               agentName={deskNameMap[`${item.gx},${item.gy}`]} />;
            case 'meeting':
              return <MeetingTable key={item.key} gx={item.gx} gy={item.gy}
                                   meetingActive={meetingActive} />;
            case 'cabinet':
              return <CabinetBox key={item.key} gx={item.gx} gy={item.gy} open={cabinetOpen} />;
            case 'coffee':
              return <CoffeeMachine key={item.key} gx={item.gx} gy={item.gy} />;
            case 'plant':
              return <Plant key={item.key} gx={item.gx} gy={item.gy} />;
            case 'agent':
              return (
                <AgentSprite
                  key={item.key}
                  agent={item.agent}
                  selected={item.agent.id === selectedId}
                  onClick={(e) => { e.stopPropagation(); onAgentClick?.(item.agent.id); }}
                />
              );
            default:
              return null;
          }
        })}
      </g>

      {/* ── Ambient overlays — fixed, not affected by camera pan/zoom ── */}
      <rect x="0" y="0" width="860" height="520"
            fill="url(#ambientCenter)" style={{ pointerEvents: 'none' }} />
      <rect x="0" y="0" width="860" height="520"
            fill="url(#ambientLight)"  style={{ pointerEvents: 'none' }} />
    </svg>
  );
});

export default Scene;
