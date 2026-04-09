/**
 * Office obstacle map for the 11×9 isometric grid.
 *
 * Visual floor plan (gx = column →, gy = row ↓):
 *
 *      0  1  2  3  4  5  6  7  8  9  10
 *   0  W  W  W  W  W  W  W  W  W  W  W
 *   1  W  .  .  .  .  .  .  .  .  .  W
 *   2  W  D  .  D  .  .  D  .  D  .  W   ← 4 agent desks
 *   3  W  .  .  .  .  .  .  .  .  .  W
 *   4  W  .  .  M  M  M  .  .  .  C  W   ← meeting table + coffee
 *   5  W  .  .  M  M  M  .  .  .  .  W
 *   6  W  D  .  .  .  .  .  .  A  .  W   ← 5th desk + filing cabinet
 *   7  W  .  .  .  .  .  .  .  .  .  W
 *   8  W  W  W  W  W  W  W  W  W  W  W
 *
 * Legend:
 *   W  Perimeter wall
 *   D  Desk (blocks movement)
 *   M  Meeting table cell (blocks movement)
 *   A  Filing cabinet / Aktenschrank (blocks movement)
 *   C  Coffee machine (blocks movement)
 */

import { findPath } from '../engine/pathfinding';

// ---------------------------------------------------------------------------
// Named cell groups (used by the renderer / scene builder)
// ---------------------------------------------------------------------------

export const WALLS = buildWalls();
export const DESKS           = [[1,2],[3,2],[6,2],[8,2],[1,6]];
export const MEETING_TABLE   = [[3,4],[4,4],[5,4],[3,5],[4,5],[5,5]];
export const FILING_CABINET  = [[8,6]];
export const COFFEE_MACHINE  = [[9,4]];

function buildWalls() {
  const cells = [];
  // Top and bottom rows
  for (let gx = 0; gx <= 10; gx++) {
    cells.push([gx, 0], [gx, 8]);
  }
  // Left and right columns (inner rows only, corners already covered)
  for (let gy = 1; gy <= 7; gy++) {
    cells.push([0, gy], [10, gy]);
  }
  return cells;
}

// ---------------------------------------------------------------------------
// Combined obstacle Set — single source of truth for pathfinding
// ---------------------------------------------------------------------------

export const OFFICE_OBSTACLES = buildObstacleSet([
  ...WALLS,
  ...DESKS,
  ...MEETING_TABLE,
  ...FILING_CABINET,
  ...COFFEE_MACHINE,
]);

function buildObstacleSet(cells) {
  return new Set(cells.map(([gx, gy]) => `${gx},${gy}`));
}

// ---------------------------------------------------------------------------
// Dev self-test: path from [1,1] → [9,6]
// ---------------------------------------------------------------------------
if (import.meta.env?.DEV !== false) {
  const path = findPath(1, 1, 9, 6, OFFICE_OBSTACLES);
  if (path.length > 0) {
    const formatted = `[1,1] → ${path.map(p => `[${p.gx},${p.gy}]`).join(' → ')}`;
    console.log(`[pathfinding] ${path.length} steps: ${formatted}`);
  } else {
    console.warn('[pathfinding] No path found from [1,1] to [9,6]');
  }
}
