import { TILE_W, TILE_H, ORIGIN_X, ORIGIN_Y, Z_SCALE } from '../data/constants';

/**
 * Grid → Screen (Painter-space)
 * gz is the vertical stacking layer (furniture, agents, …).
 * Returns pixel position of the tile's top-center point.
 *
 * @param {number} gx - grid column
 * @param {number} gy - grid row
 * @param {number} [gz=0] - height layer
 * @returns {{ x: number, y: number }}
 */
export function iso(gx, gy, gz = 0) {
  return {
    x: ORIGIN_X + (gx - gy) * (TILE_W / 2),
    y: ORIGIN_Y + (gx + gy) * (TILE_H / 2) - gz * Z_SCALE,
  };
}

/**
 * Screen → Grid  (inverse of iso at gz=0)
 * Used for click-to-move hit testing.
 *
 * @param {number} sx - screen x (relative to canvas)
 * @param {number} sy - screen y (relative to canvas)
 * @returns {{ gx: number, gy: number }}
 */
export function screenToGrid(sx, sy) {
  const rx = sx - ORIGIN_X;
  const ry = sy - ORIGIN_Y;
  return {
    gx: Math.floor(rx / TILE_W + ry / TILE_H),
    gy: Math.floor(ry / TILE_H - rx / TILE_W),
  };
}

/**
 * Sort objects by painter's algorithm so tiles/objects further from
 * the camera are drawn first (back-to-front).
 * Objects must expose { gx, gy, gz? } properties.
 *
 * @param {Array<{gx:number, gy:number, gz?:number}>} objects
 * @returns {Array}  new sorted array, originals unchanged
 */
export function sortByDepth(objects) {
  return [...objects].sort((a, b) => {
    const depthA = a.gx + a.gy + (a.gz ?? 0);
    const depthB = b.gx + b.gy + (b.gz ?? 0);
    return depthA - depthB;
  });
}

/**
 * Return the 4-directional orthogonal neighbors of a grid cell.
 * Does not clip to grid bounds — callers should filter as needed.
 *
 * @param {number} gx
 * @param {number} gy
 * @returns {Array<{gx:number, gy:number}>}
 */
export function getTileNeighbors(gx, gy) {
  return [
    { gx: gx - 1, gy },
    { gx: gx + 1, gy },
    { gx, gy: gy - 1 },
    { gx, gy: gy + 1 },
  ];
}
