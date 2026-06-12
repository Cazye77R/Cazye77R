/**
 * Agent State Machine
 *
 * Valid transitions:
 *   IDLE → WALKING → WORKING    → WALKING → IDLE
 *   IDLE → WALKING → AT_CABINET → WALKING → IDLE
 *   IDLE → WALKING → AT_COFFEE  → WALKING → IDLE
 *   IDLE → WALKING → IN_MEETING → WALKING → IDLE
 *
 * Movement is smooth: pos snaps tile-by-tile while _stepProgress (0..1)
 * lets the renderer lerp between the last snapped tile and the next waypoint.
 */

import { MOVE_SPEED, GRID_COLS, GRID_ROWS } from '../data/constants';
import { findPath } from '../engine/pathfinding';
import { OFFICE_OBSTACLES } from '../data/officeLayout';

// ---------------------------------------------------------------------------
// State constants
// ---------------------------------------------------------------------------

export const STATES = Object.freeze({
  IDLE:       'IDLE',
  WALKING:    'WALKING',
  WORKING:    'WORKING',
  AT_CABINET: 'AT_CABINET',
  AT_COFFEE:  'AT_COFFEE',
  IN_MEETING: 'IN_MEETING',
});

/** States that represent an on-site activity (not movement). */
const ACTIVITY_STATES = new Set([
  STATES.WORKING,
  STATES.AT_CABINET,
  STATES.AT_COFFEE,
  STATES.IN_MEETING,
]);

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a fresh agent machine instance.
 *
 * @param {string} id
 * @param {string} name
 * @param {string} role
 * @param {number} homeGx
 * @param {number} homeGy
 * @returns {AgentMachine}
 */
export function createAgentMachine(id, name, role, homeGx, homeGy) {
  return {
    id,
    name,
    role,

    /** Last snapped grid position (integer coords). */
    pos: { gx: homeGx, gy: homeGy },

    /** Where the agent returns after every activity. */
    homePos: { gx: homeGx, gy: homeGy },

    currentState: STATES.IDLE,

    /** Remaining waypoints (output of findPath, excludes start). */
    path: [],

    /** Index of the next tile to reach in path[]. */
    pathIndex: 0,

    /**
     * Fractional progress 0..1 toward path[pathIndex].
     * Renderer lerps between pos and path[pathIndex] using this value.
     */
    _stepProgress: 0,

    /** State to enter when the current path is fully walked. */
    targetState: null,

    /**
     * ms remaining in the current activity.
     * Set by startWalk(); decremented only while in an ACTIVITY_STATE.
     */
    activityTimer: 0,

    /** { text: string, expiresAt: number } | null */
    speech: null,

    /** 0..3 walking frame index — increments once per completed tile step. */
    animFrame: 0,
  };
}

// ---------------------------------------------------------------------------
// Pure tick — call once per rAF frame per agent
// ---------------------------------------------------------------------------

/**
 * Advance one agent by deltaMs milliseconds.
 * Returns a new agent object (original is not mutated).
 *
 * @param {AgentMachine} agent
 * @param {number}       deltaMs
 * @param {Set<string>}  obstacles
 * @returns {AgentMachine}
 */
export function tickAgent(agent, deltaMs, obstacles = OFFICE_OBSTACLES) {
  let a = { ...agent };

  // Expire speech bubble
  if (a.speech !== null && Date.now() >= a.speech.expiresAt) {
    a.speech = null;
  }

  // ── Walking ──────────────────────────────────────────────────────────────
  if (a.currentState === STATES.WALKING) {
    if (a.path.length === 0 || a.pathIndex >= a.path.length) {
      // Path exhausted → snap to final pos and transition
      if (a.path.length > 0) {
        const last = a.path[a.path.length - 1];
        a.pos = { gx: last.gx, gy: last.gy };
      }
      a.currentState = a.targetState ?? STATES.IDLE;
      a.targetState = null;
      a._stepProgress = 0;
      return a;
    }

    // Advance fractional progress toward current waypoint
    a._stepProgress += (deltaMs / 1000) * MOVE_SPEED;

    if (a._stepProgress >= 1) {
      // Tile reached — snap position and advance index
      const step = a.path[a.pathIndex];
      a.pos = { gx: step.gx, gy: step.gy };
      a.pathIndex += 1;
      a._stepProgress = 0;
      a.animFrame = (a.animFrame + 1) % 4;
    }

    return a;
  }

  // ── Activity (WORKING / AT_CABINET / AT_COFFEE / IN_MEETING) ─────────────
  if (ACTIVITY_STATES.has(a.currentState)) {
    a.activityTimer -= deltaMs;

    if (a.activityTimer <= 0) {
      // Activity done → walk back home
      const returnPath = findPath(
        a.pos.gx, a.pos.gy,
        a.homePos.gx, a.homePos.gy,
        obstacles,
      );
      a.path = returnPath;
      a.pathIndex = 0;
      a._stepProgress = 0;
      a.currentState = STATES.WALKING;
      a.targetState = STATES.IDLE;
      a.activityTimer = 0;
    }

    return a;
  }

  // ── IDLE — nothing to do ─────────────────────────────────────────────────
  return a;
}

// ---------------------------------------------------------------------------
// Command helpers (used by the hook's exposed API)
// ---------------------------------------------------------------------------

/**
 * Find the closest walkable tile adjacent to (gx, gy).
 * Checks the 4 cardinal neighbours; returns the first non-obstacle, in-bounds
 * tile, or null if all are blocked.
 *
 * @param {number}      gx
 * @param {number}      gy
 * @param {Set<string>} obstacles
 * @returns {{gx:number, gy:number}|null}
 */
export function nearestWalkable(gx, gy, obstacles) {
  const candidates = [
    { gx: gx,     gy: gy - 1 },
    { gx: gx - 1, gy: gy     },
    { gx: gx + 1, gy: gy     },
    { gx: gx,     gy: gy + 1 },
  ];
  return candidates.find(
    (c) =>
      c.gx >= 0 && c.gx < GRID_COLS &&
      c.gy >= 0 && c.gy < GRID_ROWS &&
      !obstacles.has(`${c.gx},${c.gy}`),
  ) ?? null;
}

/**
 * Start walking an agent toward (targetGx, targetGy).
 * If that tile is blocked (furniture/wall), the agent automatically walks
 * to the nearest walkable neighbour instead — so callers can pass the
 * furniture's own grid position without special-casing.
 *
 * Upon arrival the agent transitions into arrivalState and stays for
 * activityDurationMs before automatically walking home.
 *
 * Returns the agent unchanged if the destination is genuinely unreachable.
 *
 * @param {AgentMachine} agent
 * @param {number}       targetGx
 * @param {number}       targetGy
 * @param {string}       arrivalState         one of STATES
 * @param {number}       activityDurationMs
 * @param {Set<string>}  obstacles
 * @returns {AgentMachine}
 */
export function startWalk(
  agent,
  targetGx,
  targetGy,
  arrivalState = STATES.WORKING,
  activityDurationMs = 4000,
  obstacles = OFFICE_OBSTACLES,
) {
  // Resolve destination: if the tile itself is blocked, find the closest
  // walkable neighbour so callers can reference furniture positions directly.
  let destGx = targetGx, destGy = targetGy;
  if (obstacles.has(`${targetGx},${targetGy}`)) {
    const neighbour = nearestWalkable(targetGx, targetGy, obstacles);
    if (!neighbour) return agent; // fully surrounded — no-op
    destGx = neighbour.gx;
    destGy = neighbour.gy;
  }

  const alreadyThere = agent.pos.gx === destGx && agent.pos.gy === destGy;
  const path = alreadyThere
    ? []
    : findPath(agent.pos.gx, agent.pos.gy, destGx, destGy, obstacles);

  if (!alreadyThere && path.length === 0) {
    return agent; // pathfinder found no route — leave agent unchanged
  }

  return {
    ...agent,
    path,
    pathIndex: 0,
    _stepProgress: 0,
    currentState: alreadyThere ? arrivalState : STATES.WALKING,
    targetState:  alreadyThere ? null : arrivalState,
    activityTimer: activityDurationMs,
  };
}

/**
 * Force an immediate state change (no path calculation).
 * Useful for scripted events or scenario triggers.
 *
 * @param {AgentMachine} agent
 * @param {string}       state   one of STATES
 * @returns {AgentMachine}
 */
export function forceState(agent, state) {
  return { ...agent, currentState: state };
}

/**
 * Attach a speech bubble that expires after durationMs.
 *
 * @param {AgentMachine} agent
 * @param {string}       text
 * @param {number}       durationMs
 * @returns {AgentMachine}
 */
export function applySpeech(agent, text, durationMs = 3000) {
  return { ...agent, speech: { text, expiresAt: Date.now() + durationMs } };
}
