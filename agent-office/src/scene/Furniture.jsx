/**
 * Furniture.jsx — Isometric SVG furniture components
 *
 * All components receive { gx, gy, gz? } and render at the correct
 * screen position via iso(). SVG elements are drawn in isometric "flat-top"
 * projection (simplified orthographic look for pixel-art style).
 *
 * CSS keyframes are injected once via <FurnitureStyles />.
 */

import { iso } from '../engine/iso';

// ---------------------------------------------------------------------------
// Global CSS keyframes (inject once at app root)
// ---------------------------------------------------------------------------

export function FurnitureStyles() {
  return (
    <style>{`
      @keyframes steamFloat {
        0%   { transform: translateY(0px);   opacity: 0.7; }
        60%  { transform: translateY(-14px); opacity: 0.35; }
        100% { transform: translateY(-22px); opacity: 0; }
      }
      @keyframes lampBlink {
        0%, 45%  { opacity: 1; }
        50%, 95% { opacity: 0.15; }
        100%     { opacity: 1; }
      }
      @keyframes cursorBlink {
        0%, 49% { opacity: 1; }
        50%, 100% { opacity: 0; }
      }
      .steam-1 { animation: steamFloat 2.1s ease-out infinite; }
      .steam-2 { animation: steamFloat 2.1s ease-out 0.7s infinite; }
      .steam-3 { animation: steamFloat 2.1s ease-out 1.4s infinite; }
      .lamp-blink { animation: lampBlink 1.5s ease-in-out infinite; }
      .cursor-blink { animation: cursorBlink 0.9s step-end infinite; }
    `}</style>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Thin isometric top-face parallelogram (for flat surfaces). */
function IsoTop({ x, y, w, h, fill, stroke = 'none', opacity = 1 }) {
  // Diamond-ish top face: top-left, top-right, bottom-right, bottom-left
  const pts = [
    `${x},${y}`,
    `${x + w},${y + w * 0.3}`,
    `${x + w},${y + w * 0.3 + h}`,
    `${x},${y + h}`,
  ].join(' ');
  return <polygon points={pts} fill={fill} stroke={stroke} opacity={opacity} />;
}

// ---------------------------------------------------------------------------
// CabinetBox — Aktenschrank
// ---------------------------------------------------------------------------

/**
 * @param {object}  props
 * @param {number}  props.gx
 * @param {number}  props.gy
 * @param {boolean} [props.open=false]  true while an agent is AT_CABINET
 */
export function CabinetBox({ gx, gy, open = false }) {
  const { x, y } = iso(gx, gy, 0);

  // Drawer slide-out: interpolated 0 → 8px (CSS transition on the group)
  const drawerOffset = open ? 8 : 0;

  // Body dimensions (isometric-ish box)
  const bw = 28, bh = 44, bd = 10; // width, height, depth

  return (
    <g transform={`translate(${x}, ${y})`}>
      {/* ── Glow halo (blue, visible when open) ── */}
      {open && (
        <ellipse
          cx={0} cy={-bh * 0.5}
          rx={22} ry={30}
          fill="none"
          stroke="#4fc3f7"
          strokeWidth={6}
          opacity={0.35}
          style={{ filter: 'blur(4px)' }}
        />
      )}

      {/* ── Cabinet body ── */}
      {/* Left face */}
      <rect x={-bw / 2} y={-bh} width={bw} height={bh} rx={1}
            fill="#78909c" stroke="#546e7a" strokeWidth={0.8} />

      {/* Top face */}
      <polygon
        points={`${-bw/2},${-bh} ${bw/2},${-bh} ${bw/2 + bd},${-bh - bd*0.5} ${-bw/2 + bd},${-bh - bd*0.5}`}
        fill="#b0bec5" stroke="#90a4ae" strokeWidth={0.6}
      />

      {/* Right face (depth) */}
      <polygon
        points={`${bw/2},${-bh} ${bw/2},${0} ${bw/2 + bd},${-bd*0.5} ${bw/2 + bd},${-bh - bd*0.5}`}
        fill="#546e7a" stroke="#455a64" strokeWidth={0.6}
      />

      {/* ── ARCHIV label ── */}
      <text x={0} y={-bh + 8} textAnchor="middle"
            fontSize={5} fontFamily="monospace" fill="#cfd8dc" letterSpacing={0.8}>
        ARCHIV
      </text>

      {/* ── 3 drawers ── */}
      {[0, 1, 2].map((i) => {
        const dy    = -bh + 14 + i * 12; // Y of drawer face
        const slide = i === 1 && open ? drawerOffset : 0; // only middle drawer slides
        return (
          <g key={i} style={{ transition: 'transform 0.4s ease', transform: `translateX(${slide}px)` }}>
            {/* Drawer face */}
            <rect x={-bw / 2 + 2} y={dy} width={bw - 4} height={10}
                  rx={1} fill="#90a4ae" stroke="#607d8b" strokeWidth={0.7} />
            {/* Handle bar */}
            <rect x={-5} y={dy + 3} width={10} height={3}
                  rx={1.5} fill="#e0e0e0" stroke="#bdbdbd" strokeWidth={0.5} />
            {/* Handle highlight */}
            <rect x={-4} y={dy + 3.5} width={8} height={1}
                  rx={0.5} fill="white" opacity={0.6} />
          </g>
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// DeskUnit — Schreibtisch
// ---------------------------------------------------------------------------

/**
 * @param {object}  props
 * @param {number}  props.gx
 * @param {number}  props.gy
 * @param {string}  [props.agentName]  label on the monitor
 */
export function DeskUnit({ gx, gy, agentName }) {
  const { x, y } = iso(gx, gy, 0);

  return (
    <g transform={`translate(${x}, ${y})`}>
      {/* ── Desk surface (isometric top) ── */}
      <polygon
        points="-28,-8  28,-8  28,6  -28,6"
        fill="#a0745a" stroke="#7d5a45" strokeWidth={0.8}
      />
      {/* Desk front face */}
      <rect x={-28} y={0} width={56} height={16} rx={1}
            fill="#8d6347" stroke="#7d5a45" strokeWidth={0.8} />
      {/* Desk legs */}
      {[-22, 18].map((lx) => (
        <rect key={lx} x={lx} y={12} width={4} height={8}
              fill="#7d5a45" rx={1} />
      ))}

      {/* ── Paper stack (right side) ── */}
      <g transform="translate(16,-12)">
        <rect x={0} y={0} width={10} height={7} rx={0.5}
              fill="white" stroke="#ddd" strokeWidth={0.5} />
        <rect x={0} y={-1.5} width={10} height={7} rx={0.5}
              fill="#fafafa" stroke="#ddd" strokeWidth={0.5} />
        <rect x={0} y={-3} width={10} height={7} rx={0.5}
              fill="#f5f5f5" stroke="#e0e0e0" strokeWidth={0.5} />
        {/* Lines on top sheet */}
        {[0, 2, 4].map((ly) => (
          <line key={ly} x1={2} y1={ly} x2={8} y2={ly}
                stroke="#bbb" strokeWidth={0.5} />
        ))}
      </g>

      {/* ── Coffee cup ── */}
      <g transform="translate(-20,-14)">
        <rect x={0} y={2} width={7} height={7} rx={1}
              fill="#795548" stroke="#5d4037" strokeWidth={0.6} />
        {/* Cup top (dark liquid) */}
        <ellipse cx={3.5} cy={2} rx={3.5} ry={1.2}
                 fill="#4e342e" />
        {/* Handle */}
        <path d="M7,4 Q10,4 10,6 Q10,8 7,8"
              fill="none" stroke="#795548" strokeWidth={1} />
        {/* Saucer */}
        <ellipse cx={3.5} cy={9.5} rx={5} ry={1.5}
                 fill="#a1887f" />
      </g>

      {/* ── Monitor stand ── */}
      <rect x={-3} y={-26} width={6} height={14} rx={1}
            fill="#616161" />
      <rect x={-8} y={-14} width={16} height={3} rx={1}
            fill="#424242" />

      {/* ── Monitor housing ── */}
      <rect x={-18} y={-48} width={36} height={24} rx={2}
            fill="#424242" stroke="#212121" strokeWidth={0.8} />

      {/* ── Screen with gradient ── */}
      <defs>
        <linearGradient id={`screen-${gx}-${gy}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stopColor="#0d47a1" />
          <stop offset="50%"  stopColor="#1565c0" />
          <stop offset="100%" stopColor="#0a2472" />
        </linearGradient>
      </defs>
      <rect x={-15} y={-45} width={30} height={18} rx={1}
            fill={`url(#screen-${gx}-${gy})`} />

      {/* Code lines on screen */}
      {[0, 3, 6, 9, 12].map((sy, i) => (
        <rect key={sy} x={-13} y={-44 + sy}
              width={i % 3 === 0 ? 18 : i % 3 === 1 ? 24 : 12}
              height={1.5} rx={0.5}
              fill={i % 2 === 0 ? '#64b5f6' : '#a5d6a7'}
              opacity={0.8} />
      ))}

      {/* Screen cursor blink */}
      <rect x={-3} y={-35} width={1.5} height={5}
            fill="white" opacity={0.9}
            className="cursor-blink" />

      {/* ── Keyboard ── */}
      <g transform="translate(-16,-6)">
        <rect x={0} y={0} width={32} height={10} rx={1}
              fill="#616161" stroke="#424242" strokeWidth={0.5} />
        {/* Key grid: 3 rows × 5 cols */}
        {Array.from({ length: 3 }, (_, row) =>
          Array.from({ length: 5 }, (_, col) => (
            <rect
              key={`${row}-${col}`}
              x={col * 6 + 1}
              y={row * 3 + 1}
              width={4.5}
              height={2}
              rx={0.4}
              fill="#757575"
              stroke="#616161"
              strokeWidth={0.3}
            />
          ))
        )}
      </g>

      {/* Agent name tag on monitor bezel */}
      {agentName && (
        <text x={0} y={-22} textAnchor="middle"
              fontSize={4.5} fontFamily="monospace" fill="#90caf9">
          {agentName}
        </text>
      )}
    </g>
  );
}

// ---------------------------------------------------------------------------
// CoffeeMachine — Kaffeemaschine
// ---------------------------------------------------------------------------

export function CoffeeMachine({ gx, gy }) {
  const { x, y } = iso(gx, gy, 0);

  return (
    <g transform={`translate(${x}, ${y})`}>
      {/* Body */}
      <rect x={-12} y={-36} width={24} height={36} rx={2}
            fill="#37474f" stroke="#263238" strokeWidth={0.8} />
      {/* Top panel */}
      <polygon
        points="-12,-36  12,-36  17,-40  -7,-40"
        fill="#546e7a" stroke="#37474f" strokeWidth={0.6}
      />
      {/* Water tank (back, lighter grey) */}
      <rect x={5} y={-34} width={6} height={16} rx={1}
            fill="#78909c" stroke="#546e7a" strokeWidth={0.5} />

      {/* Drip tray */}
      <rect x={-13} y={-4} width={26} height={4} rx={1}
            fill="#455a64" stroke="#263238" strokeWidth={0.6} />
      {/* Tray grid */}
      {[-8,-4,0,4,8].map((tx) => (
        <line key={tx} x1={tx} y1={-4} x2={tx} y2={0}
              stroke="#37474f" strokeWidth={0.8} />
      ))}

      {/* Brew head */}
      <ellipse cx={0} cy={-16} rx={5} ry={3} fill="#263238" />
      <ellipse cx={0} cy={-15} rx={3} ry={2} fill="#1a1a1a" />

      {/* Cup slot */}
      <rect x={-6} y={-14} width={12} height={10} rx={1}
            fill="#263238" />
      {/* Mini cup */}
      <rect x={-3} y={-12} width={6} height={6} rx={0.5}
            fill="white" stroke="#e0e0e0" strokeWidth={0.4} />
      <ellipse cx={0} cy={-12} rx={3} ry={1}
               fill="#4e342e" />

      {/* Control panel */}
      <rect x={-10} y={-32} width={14} height={10} rx={1}
            fill="#455a64" />
      {/* Buttons */}
      {[[-7,-29],[-3,-29],[1,-29],[-7,-25],[-3,-25]].map(([bx,by],i) => (
        <circle key={i} cx={bx} cy={by} r={1.5}
                fill={i === 0 ? '#66bb6a' : '#78909c'}
                stroke="#263238" strokeWidth={0.4} />
      ))}

      {/* Blinking red lamp */}
      <circle cx={5} cy={-28} r={2}
              fill="#ef5350" className="lamp-blink"
              style={{ filter: 'drop-shadow(0 0 3px #ef5350)' }} />

      {/* ── Steam particles ── */}
      <g transform="translate(0,-36)">
        <circle cx={-4} cy={0} r={2.5} fill="white" className="steam-1" opacity={0} />
        <circle cx={0}  cy={0} r={2}   fill="white" className="steam-2" opacity={0} />
        <circle cx={4}  cy={0} r={2.5} fill="white" className="steam-3" opacity={0} />
      </g>
    </g>
  );
}

// ---------------------------------------------------------------------------
// MeetingTable — Besprechungstisch (3×2 Zellen: gx 3-5, gy 4-5)
// Center anchor at gx=4, gy=4 (top-left cell)
// ---------------------------------------------------------------------------

/**
 * @param {object}  props
 * @param {number}  props.gx       anchor column (3)
 * @param {number}  props.gy       anchor row    (4)
 * @param {boolean} [props.meetingActive=false]
 */
export function MeetingTable({ gx, gy, meetingActive = false }) {
  // Screen position of the anchor tile
  const { x, y } = iso(gx, gy, 0);

  return (
    <g transform={`translate(${x}, ${y})`}>
      {/* ── Whiteboard (wall behind table, slightly above) ── */}
      <g transform="translate(30, -55)">
        {/* Board body */}
        <rect x={0} y={0} width={52} height={30} rx={2}
              fill="white" stroke="#b0bec5" strokeWidth={1} />
        {/* Board frame */}
        <rect x={0} y={0} width={52} height={30} rx={2}
              fill="none" stroke="#90a4ae" strokeWidth={2.5} />
        {/* Tray at bottom */}
        <rect x={0} y={27} width={52} height={3} rx={0}
              fill="#cfd8dc" />
        {/* Marker on tray */}
        <rect x={8} y={27.5} width={10} height={2} rx={1}
              fill="#ef5350" />

        {/* Static board lines */}
        {[6, 10, 14, 18, 22].map((ly) => (
          <line key={ly} x1={4} y1={ly} x2={44} y2={ly}
                stroke="#e3f2fd" strokeWidth={0.7} opacity={0.6} />
        ))}
        {/* "Written" text lines (vary width to look handwritten) */}
        {[[4,6,28],[4,10,36],[4,14,18],[4,18,30]].map(([lx,ly,lw], i) => (
          <line key={i} x1={lx} y1={ly} x2={lx+lw} y2={ly}
                stroke="#1565c0" strokeWidth={1.2} opacity={0.75} />
        ))}

        {/* Animated writing cursor (only when meeting is active) */}
        {meetingActive && (
          <rect x={34} y={18} width={1.5} height={6}
                fill="#1565c0" className="cursor-blink" />
        )}
      </g>

      {/* ── Table surface ── */}
      {/* Top face (isometric) */}
      <polygon
        points="-32,-12  64,-12  64,12  -32,12"
        fill="#bcaaa4" stroke="#8d6e63" strokeWidth={0.8}
      />
      {/* Front face */}
      <rect x={-32} y={8} width={96} height={14} rx={1}
            fill="#a1887f" stroke="#8d6e63" strokeWidth={0.8} />

      {/* Table legs */}
      {[[-26,20],[52,20]].map(([lx,ly]) => (
        <rect key={lx} x={lx} y={ly} width={5} height={10}
              fill="#8d6e63" rx={1} />
      ))}

      {/* ── 5 Water bottles ── */}
      {[[-24,-8],[-10,-10],[6,-10],[22,-10],[38,-8]].map(([bx,by], i) => (
        <g key={i} transform={`translate(${bx},${by})`}>
          {/* Bottle body */}
          <rect x={0} y={0} width={5} height={10} rx={2}
                fill="#e3f2fd" stroke="#90caf9" strokeWidth={0.5} opacity={0.85} />
          {/* Bottle neck */}
          <rect x={1} y={-3} width={3} height={4} rx={1}
                fill="#bbdefb" stroke="#90caf9" strokeWidth={0.4} />
          {/* Cap */}
          <rect x={1} y={-5} width={3} height={2.5} rx={0.8}
                fill="#1e88e5" />
          {/* Water level (tinted) */}
          <rect x={0.5} y={5} width={4} height={4} rx={0} rx2={2}
                fill="#90caf9" opacity={0.4} />
        </g>
      ))}
    </g>
  );
}
