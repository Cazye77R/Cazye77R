import { useState, useEffect, useRef } from 'react';
import './App.css';

import { useAgentLoop }   from './hooks/useAgentLoop';
import { STATES }         from './agents/agentMachine';
import { STARTUP_AGENTS } from './data/scenarios';
import { FurnitureStyles } from './scene/Furniture';
import Scene              from './scene/Scene';

// ---------------------------------------------------------------------------
// Agent colour palette (mirrors AGENT_STYLES in scene/Agent.jsx)
// ---------------------------------------------------------------------------
const AGENT_COLORS = {
  ARIA: '#c0392b',
  BRIX: '#f39c12',
  CADE: '#27ae60',
  DORN: '#2980b9',
  ELSA: '#8e44ad',
};

// ---------------------------------------------------------------------------
// AI activity destinations
// ---------------------------------------------------------------------------
const DESTINATIONS = [
  (a) => ({ gx: a.homePos.gx, gy: a.homePos.gy, state: STATES.WORKING,    dur: 5000, msg: 'working',         speech: 'Coding...'       }),
  ()  => ({ gx: 9,            gy: 4,             state: STATES.AT_COFFEE,  dur: 3500, msg: 'coffee break',    speech: 'Need coffee!'    }),
  ()  => ({ gx: 8,            gy: 6,             state: STATES.AT_CABINET, dur: 4000, msg: 'checking files',  speech: 'Filing docs...'  }),
  ()  => ({ gx: 4,            gy: 4,             state: STATES.IN_MEETING, dur: 7000, msg: 'in meeting',      speech: 'Meeting time...' }),
  ()  => ({ gx: 3,            gy: 5,             state: STATES.IN_MEETING, dur: 7000, msg: 'brainstorming',   speech: 'Let\'s discuss!' }),
  ()  => ({ gx: 5,            gy: 5,             state: STATES.IN_MEETING, dur: 7000, msg: 'sprint planning', speech: 'Sprint plan!'    }),
];

// ---------------------------------------------------------------------------
// Sidebar sub-components
// ---------------------------------------------------------------------------

function AgentInfoPanel({ agent }) {
  return (
    <div className="agent-panel">
      <div className="agent-panel-name">{agent.name}</div>
      <div className="agent-panel-role">{agent.role}</div>
      <div className="agent-panel-row">
        <span className={`state-badge ${agent.currentState}`}>
          {agent.currentState}
        </span>
        <span className="agent-pos">
          [{agent.pos.gx}, {agent.pos.gy}]
        </span>
      </div>
      {agent.speech && (
        <div style={{ marginTop: 6, fontSize: 10, color: '#a5d6ff', fontStyle: 'italic' }}>
          &ldquo;{agent.speech.text}&rdquo;
        </div>
      )}
    </div>
  );
}

function AgentRoster({ agents, selectedId, onSelect }) {
  return (
    <div className="agent-roster">
      <div className="section-title">Agents</div>
      {agents.map((a) => (
        <div
          key={a.id}
          className={`roster-item${a.id === selectedId ? ' active' : ''}`}
          onClick={() => onSelect(a.id === selectedId ? null : a.id)}
        >
          <div className="roster-dot" style={{ background: AGENT_COLORS[a.name] ?? '#555' }} />
          <span className="roster-name">{a.name}</span>
          <span className="roster-state">{a.currentState}</span>
        </div>
      ))}
    </div>
  );
}

function LogPanel({ entries }) {
  const bottomRef = useRef(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length]);

  return (
    <div className="log-panel">
      <div className="section-title" style={{ padding: '8px 12px', borderBottom: '1px solid #30363d' }}>
        Activity Log
      </div>
      <div className="log-entries">
        {entries.map((e, i) => (
          <div key={i} className={`log-entry${i === entries.length - 1 ? ' fresh' : ''}`}>
            <span className="log-time">{e.time}</span>
            <span className="log-name" style={{ color: AGENT_COLORS[e.agent] ?? '#58a6ff' }}>
              {e.agent}
            </span>
            <span className="log-msg">{e.msg}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [running,    setRunning]    = useState(true);
  const [speed,      setSpeed]      = useState(1);
  const [selectedId, setSelectedId] = useState(null);
  const [logEntries, setLogEntries] = useState([]);

  // ── Agent loop ────────────────────────────────────────────────────────
  const { agents, moveAgent, setSpeech } = useAgentLoop(STARTUP_AGENTS, { running, speed });

  // Stable ref so the AI interval doesn't stale-close over agents
  const agentsRef = useRef(agents);
  useEffect(() => { agentsRef.current = agents; }, [agents]);

  // ── AI behaviour loop ─────────────────────────────────────────────────
  useEffect(() => {
    if (!running) return;

    const iv = setInterval(() => {
      const idle = agentsRef.current.filter((a) => a.currentState === STATES.IDLE);
      if (idle.length === 0) return;

      const agent = idle[Math.floor(Math.random() * idle.length)];
      const dest  = DESTINATIONS[Math.floor(Math.random() * DESTINATIONS.length)](agent);

      moveAgent(agent.id, dest.gx, dest.gy, dest.state, dest.dur);
      setSpeech(agent.id, dest.speech, 3000);

      const time = new Date().toLocaleTimeString('de', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
      setLogEntries((prev) =>
        [...prev, { time, agent: agent.name, msg: dest.msg }].slice(-80),
      );
    }, 2800);

    return () => clearInterval(iv);
  }, [running, moveAgent, setSpeech]);

  // ── Click-to-move ──────────────────────────────────────────────────────
  function handleTileClick(gx, gy) {
    if (!selectedId) return;
    const agent = agentsRef.current.find((a) => a.id === selectedId);
    if (!agent) return;

    moveAgent(selectedId, gx, gy, STATES.WORKING, 4000);
    setSpeech(selectedId, `Going to [${gx},${gy}]`, 2000);

    const time = new Date().toLocaleTimeString('de', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
    setLogEntries((prev) =>
      [...prev, { time, agent: agent.name, msg: `→ [${gx},${gy}]` }].slice(-80),
    );
  }

  // ── Selected agent ────────────────────────────────────────────────────
  const selectedAgent = agents.find((a) => a.id === selectedId) ?? null;

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <>
      <FurnitureStyles />

      {/* Top bar */}
      <div className="app-topbar">
        <span className="app-title">agent-office</span>

        <button
          className={`ctrl-btn${running ? ' active' : ''}`}
          onClick={() => setRunning((r) => !r)}
        >
          {running ? '⏸ Pause' : '▶ Play'}
        </button>

        <label className="speed-label">
          Speed
          <input
            type="range"
            className="speed-input"
            min={1} max={8} step={0.5}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          />
          <span className="speed-val">{speed}x</span>
        </label>
      </div>

      {/* Main content */}
      <div className="app-body">
        {/* Scene */}
        <div className="scene-wrap">
          <Scene
            agents={agents}
            selectedId={selectedId}
            onAgentClick={(id) => setSelectedId((cur) => cur === id ? null : id)}
            onTileClick={handleTileClick}
          />
        </div>

        {/* Sidebar */}
        <div className="sidebar">
          {selectedAgent && <AgentInfoPanel agent={selectedAgent} />}
          <AgentRoster
            agents={agents}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <LogPanel entries={logEntries} />
        </div>
      </div>

      {/* Hint bar */}
      <div className="hint-bar">
        <span className="hint"><span>Click agent</span> to select</span>
        <span className="hint"><span>Click tile</span> to move selected agent</span>
        <span className="hint"><span>Sidebar</span> shows live state</span>
      </div>
    </>
  );
}
