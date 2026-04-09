import { GRID_COLS, GRID_ROWS } from '../data/constants';

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Chebyshev distance — matches diagonal movement cost of 1 in all 8 dirs */
function heuristic(ax, ay, bx, by) {
  return Math.max(Math.abs(ax - bx), Math.abs(ay - by));
}

const DIRS = [
  [-1, -1], [0, -1], [1, -1],
  [-1,  0],          [1,  0],
  [-1,  1], [0,  1], [1,  1],
];

/** Binary min-heap keyed on .f (g + h) */
class MinHeap {
  constructor() { this._d = []; }
  get size() { return this._d.length; }

  push(item) {
    this._d.push(item);
    this._up(this._d.length - 1);
  }

  pop() {
    const top = this._d[0];
    const last = this._d.pop();
    if (this._d.length > 0) { this._d[0] = last; this._down(0); }
    return top;
  }

  _up(i) {
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this._d[p].f <= this._d[i].f) break;
      [this._d[p], this._d[i]] = [this._d[i], this._d[p]];
      i = p;
    }
  }

  _down(i) {
    const n = this._d.length;
    for (;;) {
      let s = i;
      const l = 2 * i + 1, r = 2 * i + 2;
      if (l < n && this._d[l].f < this._d[s].f) s = l;
      if (r < n && this._d[r].f < this._d[s].f) s = r;
      if (s === i) break;
      [this._d[s], this._d[i]] = [this._d[i], this._d[s]];
      i = s;
    }
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * A* pathfinding on the office grid (GRID_COLS × GRID_ROWS).
 *
 * - Diagonal movement allowed (Chebyshev cost = 1 per step).
 * - Corner-cutting is blocked: both adjacent cardinal tiles must be free.
 * - Returns path *excluding* start, *including* target.
 * - Returns [] if no path exists or target is an obstacle.
 *
 * @param {number}      startGx
 * @param {number}      startGy
 * @param {number}      targetGx
 * @param {number}      targetGy
 * @param {Set<string>} obstacles  Set of "gx,gy" strings
 * @returns {Array<{gx:number, gy:number}>}
 */
export function findPath(startGx, startGy, targetGx, targetGy, obstacles) {
  const key      = (x, y) => `${x},${y}`;
  const inBounds = (x, y) => x >= 0 && x < GRID_COLS && y >= 0 && y < GRID_ROWS;

  if (!inBounds(startGx, startGy) || !inBounds(targetGx, targetGy)) return [];
  if (obstacles.has(key(targetGx, targetGy))) return [];
  if (startGx === targetGx && startGy === targetGy) return [];

  const open      = new MinHeap();
  const gScore    = new Map();
  const cameFrom  = new Map();
  const closed    = new Set();

  const startKey = key(startGx, startGy);
  gScore.set(startKey, 0);
  open.push({ f: heuristic(startGx, startGy, targetGx, targetGy), gx: startGx, gy: startGy });

  while (open.size > 0) {
    const { gx, gy } = open.pop();
    const cur = key(gx, gy);

    if (gx === targetGx && gy === targetGy) {
      // Reconstruct path (excludes start node)
      const path = [];
      let node = cur;
      while (cameFrom.has(node)) {
        const [nx, ny] = node.split(',').map(Number);
        path.push({ gx: nx, gy: ny });
        node = cameFrom.get(node);
      }
      return path.reverse();
    }

    if (closed.has(cur)) continue;
    closed.add(cur);

    for (const [dx, dy] of DIRS) {
      const nx = gx + dx, ny = gy + dy;
      const nKey = key(nx, ny);

      if (!inBounds(nx, ny))      continue;
      if (obstacles.has(nKey))    continue;
      if (closed.has(nKey))       continue;

      // Prevent cutting corners through obstacles on diagonal moves
      if (dx !== 0 && dy !== 0) {
        if (obstacles.has(key(gx + dx, gy)) || obstacles.has(key(gx, gy + dy))) continue;
      }

      const tentativeG = (gScore.get(cur) ?? Infinity) + 1;
      if (tentativeG < (gScore.get(nKey) ?? Infinity)) {
        gScore.set(nKey, tentativeG);
        cameFrom.set(nKey, cur);
        open.push({ f: tentativeG + heuristic(nx, ny, targetGx, targetGy), gx: nx, gy: ny });
      }
    }
  }

  return []; // no path found
}
