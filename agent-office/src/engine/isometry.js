// Isometric math utilities

// Convert grid (col, row) to screen (x, y)
export function toScreen(col, row, tileW, tileH) {
  return {
    x: (col - row) * (tileW / 2),
    y: (col + row) * (tileH / 2),
  };
}

// Convert screen (x, y) to grid (col, row)
export function toGrid(x, y, tileW, tileH) {
  return {
    col: Math.floor(x / tileW + y / tileH),
    row: Math.floor(y / tileH - x / tileW),
  };
}
