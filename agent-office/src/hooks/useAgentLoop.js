/**
 * useAgentLoop
 *
 * Drives the simulation via requestAnimationFrame.
 * Agent state lives in a ref (agentsRef) so the rAF callback is never stale.
 * React state (agents) is synced each frame for the renderer.
 *
 * Exposed API:
 *   moveAgent(id, targetGx, targetGy, arrivalState?, durationMs?)
 *   setState(id, state)
 *   setSpeech(id, text, durationMs?)
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import { tickAgent, startWalk, forceState, applySpeech, STATES } from '../agents/agentMachine';

/**
 * @param {AgentMachine[]} initialAgents  Array produced by createAgentMachine()
 * @param {object}         options
 * @param {boolean}        options.running  Pause/resume the loop (default true)
 * @param {number}         options.speed    Global time multiplier (default 1)
 */
export function useAgentLoop(initialAgents, { running = true, speed = 1 } = {}) {
  // ── Refs ─────────────────────────────────────────────────────────────────
  /** Mutable agent array — mutated inside rAF without triggering renders */
  const agentsRef   = useRef(initialAgents);
  const rafRef      = useRef(null);
  const lastTimeRef = useRef(null);
  const runningRef  = useRef(running);
  const speedRef    = useRef(speed);

  // Keep option refs in sync without restarting the loop
  useEffect(() => { runningRef.current = running; }, [running]);
  useEffect(() => { speedRef.current = speed; },   [speed]);

  // ── React state (readonly for render) ────────────────────────────────────
  const [agents, setAgents] = useState(initialAgents);

  // ── rAF loop ─────────────────────────────────────────────────────────────
  useEffect(() => {
    function loop(timestamp) {
      rafRef.current = requestAnimationFrame(loop);

      if (!runningRef.current) {
        // Paused — keep rAF alive so we can resume without re-mounting
        lastTimeRef.current = null;
        return;
      }

      if (lastTimeRef.current === null) {
        lastTimeRef.current = timestamp;
        return;
      }

      // Cap delta to 100 ms to avoid spiral-of-death after tab focus restore
      const rawDelta = timestamp - lastTimeRef.current;
      lastTimeRef.current = timestamp;
      const delta = Math.min(rawDelta, 100) * speedRef.current;

      agentsRef.current = agentsRef.current.map((a) => tickAgent(a, delta));

      // Spread to produce a new array reference so React diffs correctly
      setAgents([...agentsRef.current]);
    }

    rafRef.current = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(rafRef.current);
      lastTimeRef.current = null;
    };
  }, []); // intentionally empty — all dynamics go through refs

  // ── Exposed commands ─────────────────────────────────────────────────────

  /**
   * Walk an agent to a grid position and enter arrivalState on arrival.
   * After activityDurationMs the agent automatically walks back home.
   *
   * @param {string} id
   * @param {number} targetGx
   * @param {number} targetGy
   * @param {string} arrivalState   defaults to STATES.WORKING
   * @param {number} durationMs     activity duration in ms (default 4000)
   */
  const moveAgent = useCallback(
    (id, targetGx, targetGy, arrivalState = STATES.WORKING, durationMs = 4000) => {
      agentsRef.current = agentsRef.current.map((a) =>
        a.id === id ? startWalk(a, targetGx, targetGy, arrivalState, durationMs) : a,
      );
    },
    [],
  );

  /**
   * Immediately force an agent into a specific state.
   * Does not compute a path — use for scripted/event-driven transitions.
   *
   * @param {string} id
   * @param {string} state  one of STATES
   */
  const setState = useCallback((id, state) => {
    agentsRef.current = agentsRef.current.map((a) =>
      a.id === id ? forceState(a, state) : a,
    );
  }, []);

  /**
   * Attach a speech bubble that auto-expires.
   *
   * @param {string} id
   * @param {string} text
   * @param {number} durationMs  (default 3000)
   */
  const setSpeech = useCallback((id, text, durationMs = 3000) => {
    agentsRef.current = agentsRef.current.map((a) =>
      a.id === id ? applySpeech(a, text, durationMs) : a,
    );
  }, []);

  return {
    /** Readonly snapshot of agent states — safe to spread into render. */
    agents,
    moveAgent,
    setState,
    setSpeech,
    /** Re-exported so consumers don't need a separate import. */
    STATES,
  };
}
