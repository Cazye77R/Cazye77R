/**
 * Scene.jsx — Isometric SVG main scene
 *
 * Features:
 *  - Camera pan (mouse drag) + zoom (scroll wheel, zoom toward cursor)
 *  - forwardRef exposes fitScreen() and screenshot() to parent
 *  - Static items memoized separately; React.memo on furniture avoids re-renders
 *  - FurnitureStyles injected inside SVG so screenshot captures animations
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
  const base = (gx + gy) % 2 === 0 ? '#e8d5b7' : '#dcc9a8';
  const fill = hovered ? '#f5e8cc' : base;
  return (
    <polygon
      points={`${x},${y - TILE_H / 2} ${x + TILE_W / 2},${y} ${x},${y + TILE_H / 2} ${x - TILE_W / 2},${y}`}
      fill={fill}
      stroke="#c4aa88"
      strokeWidth={0.4}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    />
  );
}

// ---------------------------------------------------------------------------
// WallBox
// ---------------------------------------------------------------------------

const WALL_H = 22;

function WallBox({ gx, gy }) {
  const { x, y } = iso(gx, gy);
  return (
    <g>
      <polygon
        points={`${x},${y - TILE_H / 2 - WALL_H} ${x + TILE_W / 2},${y - WALL_H} ${x},${y + TILE_H / 2 - WALL_H} ${x - TILE_W / 2},${y - WALL_H}`}
        fill="#78909c" stroke="#546e7a" strokeWidth={0.5}
      />
      <polygon
        points={`${x + TILE_W / 2},${y - WALL_H} ${x},${y + TILE_H / 2 - WALL_H} ${x},${y + TILE_H / 2} ${x + TILE_W / 2},${y}`}
        fill="#546e7a" stroke="#455a64" strokeWidth={0.5}
      />
      <polygon
        points={`${x - TILE_W / 2},${y - WALL_H} ${x},${y + TILE_H / 2 - WALL_H} ${x},${y + TILE_H / 2} ${x - TILE_W / 2},${y}`}
        fill="#607d8b" stroke="#455a64" strokeWidth={0.5}
      />
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

  // Stable ref to latest camera (used inside event handlers to avoid stale closure)
  const cameraRef = useRef(camera);
  useEffect(() => { cameraRef.current = camera; }, [camera]);

  // Drag tracking refs
  const isDragging = useRef(false);
  const hasDragged = useRef(false);
  const dragStart  = useRef({ mouseX: 0, mouseY: 0, camX: 0, camY: 0 });

  // ── Expose fit-screen + screenshot via ref ────────────────────────────────
  useImperativeHandle(ref, () => ({
    fitScreen: () => setCamera(DEFAULT_CAMERA),
    screenshot: () => {
      const svg = svgRef.current;
      if (!svg) return;
      const serializer = new XMLSerializer();
      const raw = serializer.serializeToString(svg);
      const svgStr = '<?xml version="1.0" encoding="utf-8"?>' + raw;
      const blob = new Blob([svgStr], { type: 'image/svg+xml' });
      const url  = URL.createObjectURL(blob);
      const img  = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width  = 860;
        canvas.height = 520;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, 860, 520);
        ctx.drawImage(img, 0, 0);
        canvas.toBlob((b) => {
          const a = document.createElement('a');
          a.href     = URL.createObjectURL(b);
          a.download = 'agent-office-screenshot.png';
          a.click();
          URL.revokeObjectURL(a.href);
        });
        URL.revokeObjectURL(url);
      };
      img.src = url;
    },
  }));

  // ── Global mouse listeners for pan (keeps drag working outside SVG) ───────
  useEffect(() => {
    function onMove(e) {
      if (!isDragging.current) return;
      const dx = e.clientX - dragStart.current.mouseX;
      const dy = e.clientY - dragStart.current.mouseY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasDragged.current = true;
      if (hasDragged.current) {
        setCamera((c) => ({
          ...c,
          x: dragStart.current.camX + dx,
          y: dragStart.current.camY + dy,
        }));
      }
    }
    function onUp() {
      if (isDragging.current) {
        isDragging.current      = false;
        document.body.style.cursor = '';
      }
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup',   onUp);
    };
  }, []);

  // ── Scroll-wheel zoom (non-passive so we can preventDefault) ─────────────
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    function onWheel(e) {
      e.preventDefault();
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      const rect = el.getBoundingClientRect();
      const svgW = el.viewBox.baseVal.width  || 860;
      const svgH = el.viewBox.baseVal.height || 520;
      // Mouse position in SVG-viewBox space
      const mx = (e.clientX - rect.left) * (svgW / rect.width);
      const my = (e.clientY - rect.top)  * (svgH / rect.height);
      setCamera((c) => {
        const newZoom = Math.min(1.8, Math.max(0.6, c.zoom * factor));
        // Zoom toward cursor: keep world-point under cursor fixed
        const wx = (mx - c.x) / c.zoom;
        const wy = (my - c.y) / c.zoom;
        return { x: mx - wx * newZoom, y: my - wy * newZoom, zoom: newZoom };
      });
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  // ── Mouse-down: start drag tracking ──────────────────────────────────────
  function handleMouseDown(e) {
    if (e.button !== 0) return;
    isDragging.current  = true;
    hasDragged.current  = false;
    dragStart.current   = {
      mouseX: e.clientX,
      mouseY: e.clientY,
      camX:   cameraRef.current.x,
      camY:   cameraRef.current.y,
    };
    document.body.style.cursor = 'grabbing';
  }

  // ── Click-to-move tile (suppressed if the mouse was dragged) ─────────────
  function handleSvgClick(e) {
    if (hasDragged.current) return;
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgPt = pt.matrixTransform(svg.getScreenCTM().inverse());
    const cam   = cameraRef.current;
    const worldX = (svgPt.x - cam.x) / cam.zoom;
    const worldY = (svgPt.y - cam.y) / cam.zoom;
    const { gx, gy } = screenToGrid(worldX, worldY);
    if (gx >= 0 && gx < GRID_COLS && gy >= 0 && gy < GRID_ROWS) {
      onTileClick?.(gx, gy);
    }
  }

  // ── Derived values ────────────────────────────────────────────────────────
  const cabinetOpen   = agents.some((a) => a.currentState === 'AT_CABINET');
  const meetingActive = agents.some((a) => a.currentState === 'IN_MEETING');

  const deskNameMap = useMemo(() => {
    const m = {};
    agents.forEach((a) => { m[`${a.homePos.gx},${a.homePos.gy}`] = a.name; });
    return m;
  }, [agents]);

  // Static layout items — computed once (never depends on agents)
  const staticItems = useMemo(() => {
    const items = [];
    WALLS.forEach(([gx, gy]) =>
      items.push({ gx, gy, gz: 0, type: 'wall', key: `w-${gx}-${gy}` }));
    DESKS.forEach(([gx, gy]) =>
      items.push({ gx, gy, gz: 0, type: 'desk', key: `d-${gx}-${gy}` }));
    items.push({ gx: 3, gy: 4, gz: 0, type: 'meeting', key: 'meeting' });
    FILING_CABINET.forEach(([gx, gy]) =>
      items.push({ gx, gy, gz: 0, type: 'cabinet', key: `cab-${gx}-${gy}` }));
    COFFEE_MACHINE.forEach(([gx, gy]) =>
      items.push({ gx, gy, gz: 0, type: 'coffee', key: `cof-${gx}-${gy}` }));
    return items;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Depth-sorted scene: static + agents (re-runs each frame, but sort is O(50 log 50))
  const sorted = useMemo(() => {
    const agentItems = agents.map((a) => {
      const walking = (
        a.currentState === 'WALKING' &&
        a.path.length > 0 &&
        a.pathIndex < a.path.length
      );
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
        background: 'var(--scene-bg, #1a1a2e)',
        display: 'block',
        cursor: selectedId ? 'crosshair' : 'grab',
      }}
      onClick={handleSvgClick}
      onMouseDown={handleMouseDown}
    >
      {/* CSS keyframes injected inside SVG so XMLSerializer captures them */}
      <FurnitureStyles />

      {/* All scene content wrapped in camera transform */}
      <g transform={`translate(${camera.x}, ${camera.y}) scale(${camera.zoom})`}>

        {/* ── Pass 1: floor tiles ── */}
        {Array.from({ length: GRID_ROWS }, (_, gy) =>
          Array.from({ length: GRID_COLS }, (_, gx) => {
            if (WALL_SET.has(`${gx},${gy}`)) return null;
            const isHovered = hovered?.gx === gx && hovered?.gy === gy;
            return (
              <FloorTile
                key={`ft-${gx}-${gy}`}
                gx={gx} gy={gy}
                hovered={isHovered}
                onMouseEnter={() => setHovered({ gx, gy })}
                onMouseLeave={() => setHovered(null)}
              />
            );
          })
        )}

        {/* ── Pass 2: depth-sorted (walls + furniture + agents) ── */}
        {sorted.map((item) => {
          switch (item.type) {
            case 'wall':
              return <WallBox key={item.key} gx={item.gx} gy={item.gy} />;

            case 'desk':
              return (
                <DeskUnit
                  key={item.key}
                  gx={item.gx}
                  gy={item.gy}
                  agentName={deskNameMap[`${item.gx},${item.gy}`]}
                />
              );

            case 'meeting':
              return (
                <MeetingTable
                  key={item.key}
                  gx={item.gx}
                  gy={item.gy}
                  meetingActive={meetingActive}
                />
              );

            case 'cabinet':
              return (
                <CabinetBox
                  key={item.key}
                  gx={item.gx}
                  gy={item.gy}
                  open={cabinetOpen}
                />
              );

            case 'coffee':
              return <CoffeeMachine key={item.key} gx={item.gx} gy={item.gy} />;

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
    </svg>
  );
});

export default Scene;
