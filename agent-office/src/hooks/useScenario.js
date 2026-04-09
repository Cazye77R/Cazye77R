/**
 * useScenarioRunner
 *
 * Orchestriert die scripted Szenarien aus data/scenarios.js.
 * Dispatcht Steps an useAgentLoop und wartet auf Completion
 * bevor der nächste Step startet.
 *
 * Completion-Logik (two-phase):
 *  Phase 1 – "awaitNonIdle": nach dem Dispatch wird gewartet bis
 *    mindestens ein betroffener Agent den IDLE-Zustand verlässt.
 *    (verhindert Sofort-Advance wenn React-State noch nicht aktualisiert)
 *  Phase 2 – "awaitAllIdle": sobald alle betroffenen Agents wieder
 *    IDLE sind, wird der nächste Step gestartet.
 *
 * Parallel-Steps: alle Sub-Steps gleichzeitig dispatcht, Completion
 *   wenn ALLE enthaltenen Agents wieder IDLE.
 *
 * Pause: stoppt nur die Step-Weiterleitung; laufende Animations-
 *   aktivitäten der Agents werden nicht unterbrochen.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { SCENARIOS } from '../data/scenarios';
import { STATES } from '../agents/agentMachine';

// ---------------------------------------------------------------------------
// Meeting-Zielpositionen (Hinderniszellen → nearestWalkable löst auf)
// Verteilt bis zu 5 Agents rund um den Besprechungstisch
// ---------------------------------------------------------------------------

const MEET_SPOTS = [
  { gx: 4, gy: 4 },  // → [4,3]  (Tisch-Oberkante Mitte)
  { gx: 3, gy: 5 },  // → [2,5]  (linke Seite)
  { gx: 5, gy: 5 },  // → [6,5]  (rechte Seite)
  { gx: 3, gy: 4 },  // → [3,3]  (oben links)
  { gx: 5, gy: 4 },  // → [5,3]  (oben rechts)
];

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * @param {object[]}  agents      Reaktives agents-Array aus useAgentLoop
 * @param {object}    dispatchers
 * @param {Function}  dispatchers.moveAgent
 * @param {Function}  dispatchers.setSpeech
 *
 * @returns {{
 *   start:       (scenarioId: string) => void,
 *   pause:       () => void,
 *   resume:      () => void,
 *   reset:       () => void,
 *   scenarioId:  string | null,
 *   scenario:    object | null,
 *   currentStep: object | null,
 *   stepIdx:     number,
 *   totalSteps:  number,
 *   progress:    number,   // 0..1
 *   paused:      boolean,
 *   done:        boolean,
 * }}
 */
export function useScenarioRunner(agents, { moveAgent, setSpeech }) {
  // ── React state (drives UI re-renders) ───────────────────────────────────
  const [scenarioId, setScenarioId] = useState(null);
  const [stepIdx,    setStepIdx]    = useState(-1);
  const [paused,     setPaused]     = useState(false);
  const [done,       setDone]       = useState(false);

  // ── Refs (mutation without re-render, safe inside rAF-paced effects) ────
  const scenarioRef     = useRef(null);   // active scenario object
  const stepIdxRef      = useRef(-1);     // current step index
  const pausedRef       = useRef(false);
  const doneRef         = useRef(false);
  const pendingRef      = useRef(new Set());    // agent IDs awaited
  const awaitNonIdleRef = useRef(false);  // Phase 1 flag

  // Stable refs for props that may change identity
  const moveAgentRef = useRef(moveAgent);
  const setSpeechRef = useRef(setSpeech);
  const agentsRef    = useRef(agents);

  useEffect(() => { moveAgentRef.current = moveAgent; }, [moveAgent]);
  useEffect(() => { setSpeechRef.current = setSpeech; }, [setSpeech]);
  useEffect(() => { agentsRef.current    = agents;    }, [agents]);

  // ── dispatchStep ─────────────────────────────────────────────────────────

  const dispatchStep = useCallback((step) => {
    const pending = new Set();
    const ma = moveAgentRef.current;
    const ss = setSpeechRef.current;

    function one(s) {
      const dur = s.duration ?? 4000;

      switch (s.type) {
        case 'work': {
          const a = agentsRef.current.find((ag) => ag.id === s.agent);
          if (!a) break;
          ma(s.agent, a.homePos.gx, a.homePos.gy, STATES.WORKING, dur);
          if (s.message) ss(s.agent, s.message, Math.min(dur * 0.75, 4000));
          pending.add(s.agent);
          break;
        }
        case 'cabinet': {
          ma(s.agent, 8, 6, STATES.AT_CABINET, dur);
          if (s.message) ss(s.agent, s.message, Math.min(dur * 0.75, 4000));
          pending.add(s.agent);
          break;
        }
        case 'coffee': {
          ma(s.agent, 9, 4, STATES.AT_COFFEE, dur);
          ss(s.agent, '☕ Pause!', Math.min(dur * 0.75, 2500));
          pending.add(s.agent);
          break;
        }
        case 'meet': {
          s.agents.forEach((id, i) => {
            const spot = MEET_SPOTS[i % MEET_SPOTS.length];
            ma(id, spot.gx, spot.gy, STATES.IN_MEETING, dur);
            const speech = s.speeches?.[id];
            if (speech) ss(id, speech, Math.min(dur * 0.45, 4000));
            pending.add(id);
          });
          break;
        }
        case 'parallel': {
          // Recurse into sub-steps; all collected into the same pending Set
          s.steps.forEach(one);
          break;
        }
        default:
          break;
      }
    }

    one(step);
    pendingRef.current    = pending;
    awaitNonIdleRef.current = pending.size > 0; // Phase 1 only if there's something to wait for
  }, []);

  // ── Completion watcher (runs every rAF frame via agents updates) ─────────

  useEffect(() => {
    if (!scenarioRef.current) return;
    if (pausedRef.current)    return;
    if (doneRef.current)      return;
    if (pendingRef.current.size === 0) return;

    const ids = [...pendingRef.current];

    // Phase 1: wait until at least one dispatched agent leaves IDLE
    if (awaitNonIdleRef.current) {
      const anyActive = ids.some((id) => {
        const a = agents.find((ag) => ag.id === id);
        return a && a.currentState !== STATES.IDLE;
      });
      if (anyActive) awaitNonIdleRef.current = false;
      return; // always bail here — don't check completion yet
    }

    // Phase 2: wait until ALL pending agents are back to IDLE
    const allIdle = ids.every((id) => {
      const a = agents.find((ag) => ag.id === id);
      return !a || a.currentState === STATES.IDLE;
    });

    if (!allIdle) return;

    // ── Advance ──────────────────────────────────────────────────────────
    pendingRef.current = new Set();
    const next  = stepIdxRef.current + 1;
    const steps = scenarioRef.current.steps;

    if (next < steps.length) {
      stepIdxRef.current = next;
      setStepIdx(next);
      dispatchStep(steps[next]);
    } else {
      // Scenario complete
      doneRef.current = true;
      setDone(true);
      stepIdxRef.current = -1;
      setStepIdx(-1);
    }
  }, [agents, dispatchStep]);

  // ── Public API ────────────────────────────────────────────────────────────

  /** Start a scenario by ID. Resets previous state. */
  const start = useCallback((id) => {
    const sc = SCENARIOS[id];
    if (!sc?.steps?.length) return;

    // Reset all control state
    scenarioRef.current   = sc;
    doneRef.current       = false;
    pausedRef.current     = false;
    stepIdxRef.current    = 0;
    pendingRef.current    = new Set();
    awaitNonIdleRef.current = false;

    setScenarioId(id);
    setStepIdx(0);
    setPaused(false);
    setDone(false);

    dispatchStep(sc.steps[0]);
  }, [dispatchStep]);

  /** Freeze step advancement (ongoing agent activities finish normally). */
  const pause = useCallback(() => {
    pausedRef.current = true;
    setPaused(true);
  }, []);

  /** Resume step advancement from where it was paused. */
  const resume = useCallback(() => {
    pausedRef.current = false;
    setPaused(false);
  }, []);

  /** Clear everything; agents keep their current positions. */
  const reset = useCallback(() => {
    scenarioRef.current     = null;
    pendingRef.current      = new Set();
    doneRef.current         = false;
    pausedRef.current       = false;
    awaitNonIdleRef.current = false;
    stepIdxRef.current      = -1;

    setScenarioId(null);
    setStepIdx(-1);
    setPaused(false);
    setDone(false);
  }, []);

  // ── Derived values ────────────────────────────────────────────────────────

  const scenario   = scenarioRef.current;
  const totalSteps = scenario?.steps?.length ?? 0;
  const currentStep =
    scenario && stepIdx >= 0 ? (scenario.steps[stepIdx] ?? null) : null;
  const progress =
    done       ? 1 :
    totalSteps > 0 && stepIdx >= 0 ? stepIdx / totalSteps :
    0;

  return {
    start,
    pause,
    resume,
    reset,
    scenarioId,
    scenario,
    currentStep,
    stepIdx,
    totalSteps,
    progress,
    paused,
    done,
  };
}
