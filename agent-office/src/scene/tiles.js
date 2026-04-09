// Tile and furniture definitions

export const TILE_TYPES = {
  FLOOR: 'floor',
  WALL: 'wall',
  EMPTY: 'empty',
};

export const FURNITURE = {
  DESK: { id: 'desk', label: 'Desk', blocksMovement: true },
  CHAIR: { id: 'chair', label: 'Chair', blocksMovement: false },
  SERVER: { id: 'server', label: 'Server Rack', blocksMovement: true },
  PLANT: { id: 'plant', label: 'Plant', blocksMovement: false },
};

export function createTile(type, furniture = null) {
  return { type, furniture };
}
