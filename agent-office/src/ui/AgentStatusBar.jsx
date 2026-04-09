/**
 * AgentStatusBar.jsx
 * Horizontale Leiste mit Agent-Karten. Pulsierende Indikatoren
 * wenn Agent aktiv ist. Horizontal scrollbar auf schmalen Viewports.
 */
import { AGENT_COLORS } from './EventLog';

const STATE_SHORT = {
  IDLE:       'IDLE',
  WALKING:    'LÄUFT',
  WORKING:    'ARBEIT',
  AT_COFFEE:  'KAFFEE',
  AT_CABINET: 'ARCHIV',
  IN_MEETING: 'MEETING',
};

const STATE_CLASS = {
  IDLE:       'idle',
  WALKING:    'walking',
  WORKING:    'working',
  AT_COFFEE:  'coffee',
  AT_CABINET: 'cabinet',
  IN_MEETING: 'meeting',
};

/**
 * @param {object[]}  agents
 * @param {string}    selectedId
 * @param {Function}  onSelect  (id) => void — null deselects
 */
export default function AgentStatusBar({ agents, selectedId, onSelect }) {
  return (
    <div className="agent-status-bar" role="toolbar" aria-label="Agent-Status">
      {agents.map((a) => {
        const active   = a.currentState !== 'IDLE';
        const color    = AGENT_COLORS[a.name] ?? '#555';
        const selected = a.id === selectedId;

        return (
          <button
            key={a.id}
            className={`agent-card${selected ? ' agent-card--selected' : ''}`}
            style={{ '--agent-color': color }}
            onClick={() => onSelect(selected ? null : a.id)}
            title={`${a.name} – ${a.role ?? ''}`}
            aria-pressed={selected}
          >
            {/* Status dot + pulse ring */}
            <div className="agent-card-dot-wrap">
              <div className="agent-card-dot" />
              {active && <div className="agent-card-pulse" />}
            </div>

            {/* Text info */}
            <div className="agent-card-info">
              <span className="agent-card-name">{a.name}</span>
              <span className={`agent-card-state agent-card-state--${STATE_CLASS[a.currentState] ?? 'idle'}`}>
                {STATE_SHORT[a.currentState] ?? a.currentState}
              </span>
            </div>

            {/* Speech preview */}
            {a.speech?.text && (
              <span className="agent-card-speech" title={a.speech.text}>
                {a.speech.text.slice(0, 14)}{a.speech.text.length > 14 ? '…' : ''}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
