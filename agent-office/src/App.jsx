import { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

import { useAgentLoop }        from './hooks/useAgentLoop';
import { useScenarioRunner }   from './hooks/useScenario';
import { STATES }              from './agents/agentMachine';
import { STARTUP_AGENTS }      from './data/scenarios';
import Scene                   from './scene/Scene';

import Toolbar                 from './ui/Toolbar';
import AgentStatusBar          from './ui/AgentStatusBar';
import ScenarioPanel           from './ui/ScenarioPanel';
import EventLog                from './ui/EventLog';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RANDOM_DESTINATIONS = [
  (a) => ({ gx: a.homePos.gx, gy: a.homePos.gy, state: STATES.WORKING,    dur: 5000, type: 'work',    msg: 'arbeitet...',       speech: 'Fokus!' }),
  ()  => ({ gx: 9,            gy: 4,             state: STATES.AT_COFFEE,  dur: 3500, type: 'coffee',  msg: 'kaffeepause',       speech: '☕ Pause!' }),
  ()  => ({ gx: 8,            gy: 6,             state: STATES.AT_CABINET, dur: 4000, type: 'cabinet', msg: 'unterlagen holen',  speech: 'Archiv...' }),
  ()  => ({ gx: 4,            gy: 4,             state: STATES.IN_MEETING, dur: 7000, type: 'meet',    msg: 'spontanmeeting',    speech: 'Meeting!' }),
  ()  => ({ gx: 3,            gy: 5,             state: STATES.IN_MEETING, dur: 7000, type: 'meet',    msg: 'brainstorming',     speech: 'Idee!' }),
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timestamp() {
  return new Date().toLocaleTimeString('de', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [running,    setRunning]    = useState(true);
  const [speed,      setSpeed]      = useState(1);
  const [selectedId, setSelectedId] = useState(null);
  const [logEntries, setLogEntries] = useState([]);
  const [darkMode,   setDarkMode]   = useState(true);

  // Ref to Scene — exposes fitScreen() and screenshot()
  const sceneRef = useRef(null);

  // ── Dark / Light mode ─────────────────────────────────────────────────
  useEffect(() => {
    document.body.setAttribute('data-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  // ── Agent loop ────────────────────────────────────────────────────────
  const { agents, moveAgent, setSpeech } = useAgentLoop(
    STARTUP_AGENTS,
    { running, speed },
  );

  const agentsRef = useRef(agents);
  useEffect(() => { agentsRef.current = agents; }, [agents]);

  // ── Log helper ────────────────────────────────────────────────────────
  const addLog = useCallback((entry) => {
    setLogEntries((prev) => [...prev, { time: timestamp(), ...entry }].slice(-200));
  }, []);

  // ── Scenario runner ───────────────────────────────────────────────────
  const scenario = useScenarioRunner(agents, { moveAgent, setSpeech });

  const prevStepIdx = useRef(-1);
  useEffect(() => {
    if (
      scenario.stepIdx === prevStepIdx.current ||
      scenario.stepIdx < 0 ||
      !scenario.scenario
    ) return;
    prevStepIdx.current = scenario.stepIdx;

    const step = scenario.scenario.steps[scenario.stepIdx];
    const who  = step.agents
      ? step.agents.map((id) => id.toUpperCase()).join('+')
      : step.agent?.toUpperCase() ?? '?';

    addLog({
      type: step.type,
      agent: who,
      msg:  step.topic ?? step.message ?? step.type,
    });
  }, [scenario.stepIdx, scenario.scenario, addLog]);

  // ── AI free-roam loop ─────────────────────────────────────────────────
  useEffect(() => {
    if (scenario.scenarioId || !running) return;

    const iv = setInterval(() => {
      const idle = agentsRef.current.filter((a) => a.currentState === STATES.IDLE);
      if (!idle.length) return;

      const agent = idle[Math.floor(Math.random() * idle.length)];
      const dest  = RANDOM_DESTINATIONS[
        Math.floor(Math.random() * RANDOM_DESTINATIONS.length)
      ](agent);

      moveAgent(agent.id, dest.gx, dest.gy, dest.state, dest.dur);
      setSpeech(agent.id, dest.speech, 3000);
      addLog({ type: dest.type, agent: agent.name, msg: dest.msg });
    }, 3000);

    return () => clearInterval(iv);
  }, [scenario.scenarioId, running, moveAgent, setSpeech, addLog]);

  // ── Click-to-move ─────────────────────────────────────────────────────
  function handleTileClick(gx, gy) {
    if (!selectedId) return;
    const agent = agentsRef.current.find((a) => a.id === selectedId);
    if (!agent) return;

    moveAgent(selectedId, gx, gy, STATES.WORKING, 4000);
    setSpeech(selectedId, `→ [${gx},${gy}]`, 2000);
    addLog({ type: 'work', agent: agent.name, msg: `→ [${gx},${gy}]` });
  }

  // ── Random event ──────────────────────────────────────────────────────
  const handleRandomEvent = useCallback(() => {
    const cur  = agentsRef.current;
    const idle = cur.filter((a) => a.currentState === STATES.IDLE);
    if (!idle.length) return;

    const roll = Math.random();

    if (roll < 0.35 && idle.length >= 2) {
      const [a1, a2] = idle.sort(() => Math.random() - 0.5).slice(0, 2);
      moveAgent(a1.id, 4, 4, STATES.IN_MEETING, 6000);
      moveAgent(a2.id, 3, 5, STATES.IN_MEETING, 6000);
      setSpeech(a1.id, 'Spontanmeeting!', 3500);
      setSpeech(a2.id, 'Kurze Absprache?', 3500);
      addLog({ type: 'meet', agent: `${a1.name}+${a2.name}`, msg: 'spontanmeeting' });
    } else if (roll < 0.65) {
      const a = idle[Math.floor(Math.random() * idle.length)];
      moveAgent(a.id, 9, 4, STATES.AT_COFFEE, 3000);
      setSpeech(a.id, '☕ Kaffeepause!', 2500);
      addLog({ type: 'coffee', agent: a.name, msg: 'kaffeepause!' });
    } else {
      const a = idle[Math.floor(Math.random() * idle.length)];
      moveAgent(a.id, 8, 6, STATES.AT_CABINET, 4000);
      setSpeech(a.id, 'Unterlagen holen!', 3500);
      addLog({ type: 'cabinet', agent: a.name, msg: 'unterlagen holen' });
    }
  }, [moveAgent, setSpeech, addLog]);

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <>
      <Toolbar
        running={running}
        speed={speed}
        darkMode={darkMode}
        onToggle={useCallback(() => setRunning((r) => !r), [])}
        onSpeedChange={setSpeed}
        onRandomEvent={handleRandomEvent}
        onToggleTheme={() => setDarkMode((d) => !d)}
        onFitScreen={() => sceneRef.current?.fitScreen()}
        onScreenshot={() => sceneRef.current?.screenshot()}
      />

      <AgentStatusBar
        agents={agents}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />

      <div className="app-body">
        <div className="scene-wrap">
          <Scene
            ref={sceneRef}
            agents={agents}
            selectedId={selectedId}
            onAgentClick={(id) => setSelectedId((cur) => (cur === id ? null : id))}
            onTileClick={handleTileClick}
          />
        </div>

        <div className="sidebar">
          <ScenarioPanel
            {...scenario}
            onStart={scenario.start}
            onPause={scenario.pause}
            onResume={scenario.resume}
            onReset={scenario.reset}
          />
          <EventLog entries={logEntries} />
        </div>
      </div>

      <div className="hint-bar">
        <span className="hint"><span>Agent klicken</span> → auswählen</span>
        <span className="hint"><span>Tile klicken</span> → bewegen</span>
        <span className="hint"><span>Drag</span> → kamera</span>
        <span className="hint"><span>Scroll</span> → zoom</span>
        <span className="hint"><span>Space</span> → Play/Pause</span>
      </div>
    </>
  );
}
