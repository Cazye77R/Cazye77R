/**
 * Agent.jsx — Isometric pixel-art agent renderer (SVG-based)
 *
 * Walking cycle (animFrame % 4):
 *   0 → left leg forward,  right leg back
 *   1 → neutral stance
 *   2 → right leg forward, left leg back
 *   3 → neutral stance
 *
 * Each agent variant has a unique outfit + hair/accessory layer.
 * Shadow ellipse scales with gz (height above ground).
 * Name badge visible only when selected or hovered.
 * Speech bubble auto-wraps at 18 chars / 2 lines.
 */

import { useState } from 'react';
import { iso } from '../engine/iso';

// ---------------------------------------------------------------------------
// Agent appearance catalogue
// ---------------------------------------------------------------------------

const AGENT_STYLES = {
  ARIA: {
    shirt:   '#c0392b',   // red blazer
    skin:    '#f1c27d',
    hair:    '#3d1c00',
    accessory: 'ponytail',
  },
  BRIX: {
    shirt:   '#f39c12',   // yellow pullover
    skin:    '#fad7a0',
    hair:    '#1a1a1a',
    accessory: 'glasses',
  },
  CADE: {
    shirt:   '#27ae60',   // green hoodie
    skin:    '#c68642',
    hair:    '#5d3317',
    accessory: 'headset',
  },
  DORN: {
    shirt:   '#2980b9',   // blue vest
    skin:    '#f0d9b5',
    hair:    '#2c2c2c',
    accessory: 'vest-stripe',
  },
  ELSA: {
    shirt:   '#8e44ad',   // purple work jacket
    skin:    '#ffe0bd',
    hair:    '#8b0000',
    accessory: 'braid',
  },
};

/** Resolve style from agent name (falls back to a default). */
function resolveStyle(name) {
  const key = name?.toUpperCase();
  return AGENT_STYLES[key] ?? { shirt: '#7f8c8d', skin: '#f1c27d', hair: '#3d2b1f', accessory: null };
}

// ---------------------------------------------------------------------------
// Sub-component: accessory layer
// ---------------------------------------------------------------------------

function Accessory({ type, skin, hair, cx }) {
  if (!type) return null;

  switch (type) {
    case 'ponytail':
      // Ponytail swinging to the right
      return (
        <>
          <ellipse cx={cx + 4} cy={-20} rx={3} ry={6} fill={hair} />
          <rect    x={cx + 5}  y={-23} width={2} height={5} rx={1} fill={hair} />
        </>
      );

    case 'glasses':
      // Simple rectangular glasses
      return (
        <>
          <rect x={cx - 6} y={-27} width={4} height={3} rx={1} fill="none" stroke="#333" strokeWidth={0.8} />
          <rect x={cx + 2} y={-27} width={4} height={3} rx={1} fill="none" stroke="#333" strokeWidth={0.8} />
          <line x1={cx - 2} y1={-25.5} x2={cx + 2} y2={-25.5} stroke="#333" strokeWidth={0.8} />
        </>
      );

    case 'headset':
      // Headset arc + mic
      return (
        <>
          <path d={`M ${cx - 7} -28 a7,7 0 0,1 14,0`} fill="none" stroke="#555" strokeWidth={1.5} />
          <rect x={cx - 8}  y={-29} width={2} height={4} rx={1} fill="#555" />
          <rect x={cx + 6}  y={-29} width={2} height={4} rx={1} fill="#555" />
          {/* mic arm */}
          <path d={`M ${cx + 6} -27 q4,2 3,5`} fill="none" stroke="#555" strokeWidth={1} />
          <circle cx={cx + 9} cy={-22} r={1} fill="#555" />
        </>
      );

    case 'vest-stripe':
      // Thin yellow safety-vest stripe across the torso
      return (
        <>
          <rect x={cx - 6} y={-16} width={12} height={2} rx={0.5} fill="#f1c40f" opacity={0.9} />
          <rect x={cx - 6} y={-12} width={12} height={2} rx={0.5} fill="#f1c40f" opacity={0.9} />
        </>
      );

    case 'braid':
      // Long braid on the left side
      return (
        <>
          <rect x={cx - 7}  y={-23} width={3} height={10} rx={1} fill={hair} />
          <rect x={cx - 6}  y={-13} width={2} height={5}  rx={1} fill={hair} />
        </>
      );

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Sub-component: walking legs
// ---------------------------------------------------------------------------

/**
 * Returns leg/foot rects based on the 4-frame walking cycle.
 * cx = horizontal center of the body.
 */
function Legs({ frame, shirt, cx }) {
  const darkShirt = shirt;  // trousers same dark as shirt base
  const trousers  = '#2c3e50';

  // Offsets: [leftLegY, rightLegY, leftFootX, rightFootX]
  // Frame 0: left forward (down), right back (up)
  // Frame 1: neutral
  // Frame 2: right forward, left back
  // Frame 3: neutral
  const configs = [
    { lY: 2, rY: -2, lFx: -2, rFx: 2 },    // frame 0 — left fwd
    { lY: 0, rY: 0,  lFx: -3, rFx: 3 },    // frame 1 — neutral
    { lY: -2, rY: 2, lFx: -2, rFx: 2 },    // frame 2 — right fwd
    { lY: 0, rY: 0,  lFx: -3, rFx: 3 },    // frame 3 — neutral
  ];
  const cfg = configs[frame % 4];

  return (
    <>
      {/* Left leg */}
      <rect x={cx - 5}  y={-5 + cfg.lY} width={4} height={7} rx={1} fill={trousers} />
      {/* Right leg */}
      <rect x={cx + 1}  y={-5 + cfg.rY} width={4} height={7} rx={1} fill={trousers} />
      {/* Left foot */}
      <rect x={cx - 5 + cfg.lFx} y={2 + cfg.lY} width={5} height={2} rx={1} fill="#1a252f" />
      {/* Right foot */}
      <rect x={cx + 1 + cfg.rFx} y={2 + cfg.rY} width={5} height={2} rx={1} fill="#1a252f" />
    </>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: speech bubble
// ---------------------------------------------------------------------------

const MAX_LINE_LEN = 18;

function wrapText(text) {
  if (!text) return [];
  const words = text.split(' ');
  const lines = [];
  let line = '';
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length > MAX_LINE_LEN && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
    if (lines.length === 2) break; // hard cap at 2 lines
  }
  if (line && lines.length < 2) lines.push(line);
  return lines;
}

function SpeechBubble({ text, cx }) {
  const lines = wrapText(text);
  if (lines.length === 0) return null;

  const charW  = 5.5;
  const lineH  = 11;
  const padX   = 6;
  const padY   = 4;
  const maxLen = Math.max(...lines.map((l) => l.length));
  const bw     = maxLen * charW + padX * 2;
  const bh     = lines.length * lineH + padY * 2;
  const bx     = cx - bw / 2;
  const by     = -46 - bh;

  return (
    <g>
      {/* Bubble body */}
      <rect x={bx} y={by} width={bw} height={bh} rx={5} fill="white" stroke="#333" strokeWidth={0.8} />
      {/* Tail */}
      <polygon
        points={`${cx - 3},${by + bh} ${cx + 3},${by + bh} ${cx},${by + bh + 6}`}
        fill="white"
        stroke="#333"
        strokeWidth={0.8}
      />
      {/* Text lines */}
      {lines.map((line, i) => (
        <text
          key={i}
          x={cx}
          y={by + padY + (i + 1) * lineH - 2}
          textAnchor="middle"
          fontSize={9}
          fontFamily="monospace"
          fill="#222"
        >
          {line}
        </text>
      ))}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * @param {object}  props
 * @param {object}  props.agent    AgentMachine instance
 * @param {number}  [props.gz=0]   Height layer (for shadow scale)
 * @param {boolean} [props.selected]
 * @param {Function} [props.onClick]
 */
export default function Agent({ agent, gz = 0, selected = false, onClick }) {
  const [hovered, setHovered] = useState(false);

  const style   = resolveStyle(agent.name);
  const frame   = agent.animFrame ?? 0;

  // Interpolated screen position
  const isWalking = agent.currentState === 'WALKING' &&
                    agent.path.length > 0 &&
                    agent.pathIndex < agent.path.length;

  let screenPos;
  if (isWalking) {
    const cur  = iso(agent.pos.gx, agent.pos.gy, gz);
    const next = iso(agent.path[agent.pathIndex].gx, agent.path[agent.pathIndex].gy, gz);
    const t    = agent._stepProgress ?? 0;
    screenPos = {
      x: cur.x + (next.x - cur.x) * t,
      y: cur.y + (next.y - cur.y) * t,
    };
  } else {
    screenPos = iso(agent.pos.gx, agent.pos.gy, gz);
  }

  const { x, y } = screenPos;

  // Shadow shrinks as gz increases
  const shadowRy = Math.max(2, 5 - gz * 1.2);
  const shadowRx = shadowRy * 2.5;

  // cx/cy relative to the SVG group origin (which is translated to x,y)
  const cx = 0;

  const showBadge = selected || hovered;

  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ cursor: 'pointer' }}
    >
      {/* ── Shadow ──────────────────────────────────────────────────── */}
      <ellipse
        cx={cx}
        cy={4}
        rx={shadowRx}
        ry={shadowRy}
        fill="rgba(0,0,0,0.18)"
      />

      {/* ── Legs / feet ──────────────────────────────────────────────── */}
      <Legs frame={frame} shirt={style.shirt} cx={cx} />

      {/* ── Torso ────────────────────────────────────────────────────── */}
      <rect
        x={cx - 6}
        y={-18}
        width={12}
        height={13}
        rx={2}
        fill={style.shirt}
      />

      {/* ── Arms (simple rects, swing opposite to legs) ───────────────── */}
      {/* Left arm */}
      <rect
        x={cx - 9}
        y={-17 + (frame === 0 ? -1 : frame === 2 ? 1 : 0)}
        width={3}
        height={8}
        rx={1}
        fill={style.shirt}
      />
      {/* Right arm */}
      <rect
        x={cx + 6}
        y={-17 + (frame === 2 ? -1 : frame === 0 ? 1 : 0)}
        width={3}
        height={8}
        rx={1}
        fill={style.shirt}
      />

      {/* ── Head ─────────────────────────────────────────────────────── */}
      <ellipse cx={cx} cy={-24} rx={6} ry={7} fill={style.skin} />

      {/* Hair */}
      <ellipse cx={cx} cy={-29} rx={6} ry={4} fill={style.hair} />

      {/* Eyes */}
      <circle cx={cx - 2} cy={-24} r={1}   fill="#222" />
      <circle cx={cx + 2} cy={-24} r={1}   fill="#222" />

      {/* ── Accessory ────────────────────────────────────────────────── */}
      <Accessory type={style.accessory} skin={style.skin} hair={style.hair} cx={cx} />

      {/* ── Name badge ───────────────────────────────────────────────── */}
      {showBadge && (
        <g>
          <rect
            x={cx - 16}
            y={-42}
            width={32}
            height={10}
            rx={3}
            fill="rgba(0,0,0,0.65)"
          />
          <text
            x={cx}
            y={-34}
            textAnchor="middle"
            fontSize={7}
            fontFamily="monospace"
            fill="white"
          >
            {agent.name}
          </text>
        </g>
      )}

      {/* ── Speech bubble ─────────────────────────────────────────────── */}
      {agent.speech?.text && (
        <SpeechBubble text={agent.speech.text} cx={cx} />
      )}
    </g>
  );
}
