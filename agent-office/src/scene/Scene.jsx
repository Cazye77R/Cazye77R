/**
 * Scene.jsx — Isometrische SVG-Hauptszene
 *
 * Render-Pipeline:
 *  1. Bodenplatten (alle Nicht-Wand-Felder) — keine Tiefensortierung nötig
 *  2. Tiefensortierte Objekte: Wand-Boxen + Möbel + Agents
 *
 * Click-to-Move: SVG-Koordinaten werden via getScreenCTM korrekt skaliert
 * und mit screenToGrid in Grid-Positionen umgerechnet.
 */

import { useRef, useState, useMemo } from 'react';
import { iso, sortByDepth, screenToGrid } from '../engine/iso';
import { TILE_W, TILE_H, GRID_COLS, GRID_ROWS } from '../data/constants';
import {
  WALLS, DESKS, MEETING_TABLE, FILING_CABINET, COFFEE_MACHINE,
} from '../data/officeLayout';
import { DeskUnit, CabinetBox, CoffeeMachine, MeetingTable } from './Furniture';
import AgentSprite from './Agent';

// Pre-built lookup sets
const WALL_SET    = new Set(WALLS.map(([gx, gy]) => `${gx},${gy}`));
const MEETING_SET = new Set(MEETING_TABLE.map(([gx, gy]) => `${gx},${gy}`));

// ---------------------------------------------------------------------------
// FloorTile
// ---------------------------------------------------------------------------

function FloorTile({ gx, gy, hovered, onMouseEnter, onMouseLeave }) {
  const { x, y } = iso(gx, gy);
  const base  = (gx + gy) % 2 === 0 ? '#e8d5b7' : '#dcc9a8';
  const fill  = hovered ? '#f5e8cc' : base;
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
      {/* Top face */}
      <polygon
        points={`
          ${x},${y - TILE_H / 2 - WALL_H}
          ${x + TILE_W / 2},${y - WALL_H}
          ${x},${y + TILE_H / 2 - WALL_H}
          ${x - TILE_W / 2},${y - WALL_H}
        `}
        fill="#78909c" stroke="#546e7a" strokeWidth={0.5}
      />
      {/* Right face */}
      <polygon
        points={`
          ${x + TILE_W / 2},${y - WALL_H}
          ${x},${y + TILE_H / 2 - WALL_H}
          ${x},${y + TILE_H / 2}
          ${x + TILE_W / 2},${y}
        `}
        fill="#546e7a" stroke="#455a64" strokeWidth={0.5}
      />
      {/* Left face */}
      <polygon
        points={`
          ${x - TILE_W / 2},${y - WALL_H}
          ${x},${y + TILE_H / 2 - WALL_H}
          ${x},${y + TILE_H / 2}
          ${x - TILE_W / 2},${y}
        `}
        fill="#607d8b" stroke="#455a64" strokeWidth={0.5}
      />
    </g>
  );
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------

/**
 * @param {object}    props
 * @param {object[]}  props.agents        Array von AgentMachine-Objekten
 * @param {string}    [props.selectedId]  ID des ausgewählten Agents
 * @param {Function}  [props.onAgentClick]  (id) => void
 * @param {Function}  [props.onTileClick]   (gx, gy) => void
 */
export default function Scene({ agents, selectedId, onAgentClick, onTileClick }) {
  const svgRef   = useRef(null);
  const [hovered, setHovered] = useState(null); // {gx, gy}

  const cabinetOpen  = agents.some((a) => a.currentState === 'AT_CABINET');
  const meetingActive = agents.some((a) => a.currentState === 'IN_MEETING');

  // Map homePos → agentName for desk labels
  const deskNameMap = useMemo(() => {
    const m = {};
    agents.forEach((a) => { m[`${a.homePos.gx},${a.homePos.gy}`] = a.name; });
    return m;
  }, [agents]);

  // Build depth-sorted renderable list (walls + furniture + agents)
  const sorted = useMemo(() => {
    const items = [];

    // Wall boxes
    WALLS.forEach(([gx, gy]) => {
      items.push({ gx, gy, gz: 0, type: 'wall', key: `w-${gx}-${gy}` });
    });

    // Desks
    DESKS.forEach(([gx, gy]) => {
      items.push({ gx, gy, gz: 0, type: 'desk', key: `d-${gx}-${gy}` });
    });

    // Meeting table (single component, anchored at top-left cell)
    items.push({ gx: 3, gy: 4, gz: 0, type: 'meeting', key: 'meeting' });

    // Filing cabinet
    FILING_CABINET.forEach(([gx, gy]) => {
      items.push({ gx, gy, gz: 0, type: 'cabinet', key: `cab-${gx}-${gy}` });
    });

    // Coffee machine
    COFFEE_MACHINE.forEach(([gx, gy]) => {
      items.push({ gx, gy, gz: 0, type: 'coffee', key: `cof-${gx}-${gy}` });
    });

    // Agents — use interpolated position for depth sort
    agents.forEach((a) => {
      const walking = (
        a.currentState === 'WALKING' &&
        a.path.length > 0 &&
        a.pathIndex < a.path.length
      );
      const t   = a._stepProgress ?? 0;
      const egx = walking ? a.pos.gx + (a.path[a.pathIndex].gx - a.pos.gx) * t : a.pos.gx;
      const egy = walking ? a.pos.gy + (a.path[a.pathIndex].gy - a.pos.gy) * t : a.pos.gy;
      items.push({ gx: egx, gy: egy, gz: 1, type: 'agent', agent: a, key: `ag-${a.id}` });
    });

    return sortByDepth(items);
  }, [agents]);

  // ── Click handler: screen → SVG coords → grid ──────────────────────────
  function handleSvgClick(e) {
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgPt = pt.matrixTransform(svg.getScreenCTM().inverse());
    const { gx, gy } = screenToGrid(svgPt.x, svgPt.y);
    if (gx >= 0 && gx < GRID_COLS && gy >= 0 && gy < GRID_ROWS) {
      onTileClick?.(gx, gy);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <svg
      ref={svgRef}
      width="100%"
      height="100%"
      viewBox="0 0 860 520"
      preserveAspectRatio="xMidYMid meet"
      style={{ background: '#1a1a2e', display: 'block' }}
      onClick={handleSvgClick}
    >
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

      {/* ── Pass 2: depth-sorted objects ── */}
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
    </svg>
  );
}
