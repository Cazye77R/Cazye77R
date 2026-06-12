/**
 * Agent.jsx — Isometric pixel-art agent renderer (SVG-based)
 *
 * Walking cycle (animFrame % 4):
 *   0 → left leg forward,  right leg back
 *   1 → neutral stance
 *   2 → right leg forward, left leg back
 *   3 → neutral stance
 *
 * Sprites are ~35% larger than v1.  Selection shows a dashed glow ring.
 * Speech bubble has a coloured background tinted to agent shirt colour.
 */

import { useState } from 'react';
import { iso } from '../engine/iso';

// ---------------------------------------------------------------------------
// Agent appearance catalogue
// ---------------------------------------------------------------------------

const AGENT_STYLES = {
  ARIA: { shirt: '#c0392b', skin: '#f1c27d', hair: '#3d1c00', accessory: 'ponytail' },
  BRIX: { shirt: '#e8920a', skin: '#fad7a0', hair: '#1a1a1a', accessory: 'glasses'  },
  CADE: { shirt: '#27ae60', skin: '#c68642', hair: '#5d3317', accessory: 'headset'  },
  DORN: { shirt: '#2980b9', skin: '#f0d9b5', hair: '#2c2c2c', accessory: 'vest-stripe' },
  ELSA: { shirt: '#8e44ad', skin: '#ffe0bd', hair: '#8b0000', accessory: 'braid'    },
};

function resolveStyle(name) {
  return AGENT_STYLES[name?.toUpperCase()] ??
    { shirt: '#607d8b', skin: '#f1c27d', hair: '#3d2b1f', accessory: null };
}

// ---------------------------------------------------------------------------
// Accessory layer
// ---------------------------------------------------------------------------

function Accessory({ type, skin, hair, cx }) {
  if (!type) return null;
  switch (type) {
    case 'ponytail':
      return (
        <>
          <ellipse cx={cx + 5}  cy={-26} rx={3.5} ry={7} fill={hair} />
          <rect    x={cx + 6}   y={-30}  width={2.5} height={6} rx={1.2} fill={hair} />
        </>
      );
    case 'glasses':
      return (
        <>
          <rect x={cx - 8} y={-36} width={5.5} height={3.5} rx={1.2} fill="none" stroke="#333" strokeWidth={0.9} />
          <rect x={cx + 2} y={-36} width={5.5} height={3.5} rx={1.2} fill="none" stroke="#333" strokeWidth={0.9} />
          <line x1={cx - 2.5} y1={-34} x2={cx + 2} y2={-34} stroke="#333" strokeWidth={0.9} />
          <line x1={cx - 8}   y1={-34} x2={cx - 10} y2={-33} stroke="#333" strokeWidth={0.8} />
          <line x1={cx + 7.5} y1={-34} x2={cx + 9.5} y2={-33} stroke="#333" strokeWidth={0.8} />
        </>
      );
    case 'headset':
      return (
        <>
          <path d={`M ${cx - 9} -37 a9,9 0 0,1 18,0`} fill="none" stroke="#555" strokeWidth={2} />
          <rect x={cx - 11} y={-38} width={2.5} height={5} rx={1.2} fill="#444" />
          <rect x={cx + 8}  y={-38} width={2.5} height={5} rx={1.2} fill="#444" />
          <path d={`M ${cx + 9} -35 q5,3 4,7`} fill="none" stroke="#555" strokeWidth={1.2} />
          <circle cx={cx + 13} cy={-28} r={1.3} fill="#555" />
        </>
      );
    case 'vest-stripe':
      return (
        <>
          <rect x={cx - 8} y={-21} width={16} height={2.5} rx={0.8} fill="#f1c40f" opacity={0.95} />
          <rect x={cx - 8} y={-15} width={16} height={2.5} rx={0.8} fill="#f1c40f" opacity={0.95} />
        </>
      );
    case 'braid':
      return (
        <>
          <rect x={cx - 9}  y={-30} width={3.5} height={13} rx={1.5} fill={hair} />
          <rect x={cx - 8}  y={-17} width={2.5} height={6}  rx={1}   fill={hair} />
          <ellipse cx={cx - 8} cy={-11} rx={2} ry={1.5} fill={hair} />
        </>
      );
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Walking legs (scaled up)
// ---------------------------------------------------------------------------

function Legs({ frame, cx }) {
  const trousers = '#263040';
  const shoe     = '#1a252f';
  const configs = [
    { lY: 2.5, rY: -2.5, lFx: -2, rFx: 2 },
    { lY: 0,   rY: 0,    lFx: -4, rFx: 4 },
    { lY: -2.5, rY: 2.5, lFx: -2, rFx: 2 },
    { lY: 0,   rY: 0,    lFx: -4, rFx: 4 },
  ];
  const cfg = configs[frame % 4];

  return (
    <>
      <rect x={cx - 7}  y={-6 + cfg.lY} width={5} height={9}  rx={1.5} fill={trousers} />
      <rect x={cx + 2}  y={-6 + cfg.rY} width={5} height={9}  rx={1.5} fill={trousers} />
      <rect x={cx - 7 + cfg.lFx} y={3 + cfg.lY} width={6} height={2.5} rx={1.2} fill={shoe} />
      <rect x={cx + 2  + cfg.rFx} y={3 + cfg.rY} width={6} height={2.5} rx={1.2} fill={shoe} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Speech bubble (styled with agent tint)
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
    if (lines.length === 2) break;
  }
  if (line && lines.length < 2) lines.push(line);
  return lines;
}

function SpeechBubble({ text, cx, tint }) {
  const lines = wrapText(text);
  if (!lines.length) return null;

  const charW  = 5.5;
  const lineH  = 11;
  const padX   = 7;
  const padY   = 5;
  const maxLen = Math.max(...lines.map((l) => l.length));
  const bw     = maxLen * charW + padX * 2;
  const bh     = lines.length * lineH + padY * 2;
  const bx     = cx - bw / 2;
  const by     = -58 - bh;

  return (
    <g>
      {/* Bubble shadow */}
      <rect x={bx + 1} y={by + 2} width={bw} height={bh} rx={6}
            fill="rgba(0,0,0,0.25)" />
      {/* Bubble body */}
      <rect x={bx} y={by} width={bw} height={bh} rx={6}
            fill="white" stroke={tint} strokeWidth={1} />
      {/* Tint stripe at top */}
      <rect x={bx} y={by} width={bw} height={4} rx={6}
            fill={tint} opacity={0.3} />
      {/* Tail */}
      <polygon
        points={`${cx - 4},${by + bh} ${cx + 4},${by + bh} ${cx},${by + bh + 7}`}
        fill="white"
        stroke={tint}
        strokeWidth={1}
      />
      {/* Mask tail stroke seam */}
      <line x1={cx - 3} y1={by + bh} x2={cx + 3} y2={by + bh}
            stroke="white" strokeWidth={1.5} />
      {/* Text */}
      {lines.map((line, i) => (
        <text
          key={i}
          x={cx}
          y={by + padY + (i + 1) * lineH - 1}
          textAnchor="middle"
          fontSize={9}
          fontFamily="monospace"
          fill="#1a1a2e"
          fontWeight="600"
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

export default function AgentSprite({ agent, gz = 0, selected = false, onClick }) {
  const [hovered, setHovered] = useState(false);

  const style = resolveStyle(agent.name);
  const frame = agent.animFrame ?? 0;

  // Interpolated screen position
  const isWalking = agent.currentState === 'WALKING' &&
                    agent.path.length > 0 &&
                    agent.pathIndex < agent.path.length;

  let screenPos;
  if (isWalking) {
    const cur  = iso(agent.pos.gx, agent.pos.gy, gz);
    const next = iso(agent.path[agent.pathIndex].gx, agent.path[agent.pathIndex].gy, gz);
    const t    = agent._stepProgress ?? 0;
    screenPos  = { x: cur.x + (next.x - cur.x) * t, y: cur.y + (next.y - cur.y) * t };
  } else {
    screenPos = iso(agent.pos.gx, agent.pos.gy, gz);
  }

  const { x, y } = screenPos;
  const shadowRy  = Math.max(2.5, 7 - gz * 1.5);
  const shadowRx  = shadowRy * 2.6;
  const cx        = 0;
  const showBadge = selected || hovered;

  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ cursor: 'pointer' }}
    >
      {/* ── Selection glow ring (behind everything) ─────────────────── */}
      {selected && (
        <>
          <ellipse cx={cx} cy={3} rx={shadowRx + 6} ry={shadowRy + 3}
                   fill={style.shirt} opacity={0.12} />
          <circle  cx={cx} cy={-20} r={22}
                   fill="none"
                   stroke={style.shirt}
                   strokeWidth={1.8}
                   opacity={0.65}
                   strokeDasharray="5 3" />
        </>
      )}

      {/* ── Shadow ──────────────────────────────────────────────────── */}
      <ellipse cx={cx} cy={5} rx={shadowRx} ry={shadowRy}
               fill="rgba(0,0,0,0.22)" />

      {/* ── Legs ────────────────────────────────────────────────────── */}
      <Legs frame={frame} cx={cx} />

      {/* ── Torso ───────────────────────────────────────────────────── */}
      <rect x={cx - 8} y={-24} width={16} height={18} rx={3} fill={style.shirt} />
      {/* Shirt highlight */}
      <rect x={cx - 7} y={-23} width={6} height={4} rx={1.5}
            fill="white" opacity={0.12} />

      {/* ── Arms ────────────────────────────────────────────────────── */}
      <rect x={cx - 12} y={-23 + (frame === 0 ? -1.5 : frame === 2 ? 1.5 : 0)}
            width={4} height={11} rx={1.5} fill={style.shirt} />
      <rect x={cx + 8}  y={-23 + (frame === 2 ? -1.5 : frame === 0 ? 1.5 : 0)}
            width={4} height={11} rx={1.5} fill={style.shirt} />

      {/* ── Head ────────────────────────────────────────────────────── */}
      <ellipse cx={cx} cy={-33} rx={8} ry={9} fill={style.skin} />
      {/* Neck */}
      <rect x={cx - 3} y={-25} width={6} height={3} rx={1} fill={style.skin} />

      {/* ── Hair ────────────────────────────────────────────────────── */}
      <ellipse cx={cx} cy={-39} rx={8} ry={5} fill={style.hair} />

      {/* ── Eyes ────────────────────────────────────────────────────── */}
      <circle cx={cx - 2.5} cy={-33} r={1.3} fill="#111" />
      <circle cx={cx + 2.5} cy={-33} r={1.3} fill="#111" />
      {/* Eye highlights */}
      <circle cx={cx - 2}   cy={-33.5} r={0.5} fill="white" opacity={0.8} />
      <circle cx={cx + 3}   cy={-33.5} r={0.5} fill="white" opacity={0.8} />

      {/* ── Accessory ───────────────────────────────────────────────── */}
      <Accessory type={style.accessory} skin={style.skin} hair={style.hair} cx={cx} />

      {/* ── Name badge ──────────────────────────────────────────────── */}
      {showBadge && (
        <g>
          <rect x={cx - 18} y={-54} width={36} height={12} rx={4}
                fill="rgba(8,12,18,0.82)" stroke={style.shirt} strokeWidth={0.8} />
          <text x={cx} y={-44} textAnchor="middle"
                fontSize={7.5} fontFamily="monospace" fill="white" fontWeight="600">
            {agent.name}
          </text>
        </g>
      )}

      {/* ── Speech bubble ───────────────────────────────────────────── */}
      {agent.speech?.text && (
        <SpeechBubble text={agent.speech.text} cx={cx} tint={style.shirt} />
      )}
    </g>
  );
}
