/**
 * EventLog.jsx
 * Virtualized activity log: max 20 DOM-Einträge.
 * Neue Einträge werden mit slideIn animiert.
 */
import { useRef, useEffect } from 'react';

const TYPE_ICONS = {
  work:    '🏗',
  cabinet: '🗄',
  coffee:  '☕',
  meet:    '👥',
};

export const AGENT_COLORS = {
  ARIA: '#c0392b',
  BRIX: '#f39c12',
  CADE: '#27ae60',
  DORN: '#2980b9',
  ELSA: '#8e44ad',
};

const WINDOW = 20;

/**
 * @param {object[]} entries  { time, agent, msg, type? }
 */
export default function EventLog({ entries = [] }) {
  const bottomRef = useRef(null);
  const visible   = entries.slice(-WINDOW);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length]);

  return (
    <div className="event-log">
      <div className="event-log-header">
        <span className="section-title">Event Log</span>
        {entries.length > 0 && (
          <span className="event-log-count">{entries.length}</span>
        )}
      </div>

      <div className="event-log-list">
        {visible.map((e, i) => {
          const isFresh = i === visible.length - 1;
          return (
            <div
              key={entries.length - WINDOW + i}
              className={`event-entry${isFresh ? ' event-entry--fresh' : ''}`}
              data-type={e.type}
            >
              <span className="event-icon" aria-hidden="true">
                {TYPE_ICONS[e.type] ?? '·'}
              </span>
              <span className="event-time">{e.time}</span>
              <span
                className="event-name"
                style={{ color: AGENT_COLORS[e.agent] ?? '#58a6ff' }}
              >
                {e.agent}
              </span>
              <span className="event-msg">{e.msg}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
