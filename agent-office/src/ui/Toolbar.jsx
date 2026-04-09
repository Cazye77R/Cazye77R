/**
 * Toolbar.jsx
 * Globale Steuerleiste:
 *  - Play/Pause mit [Space]-Shortcut
 *  - Geschwindigkeit: 0.5x / 1x / 2x / 4x
 *  - Zufalls-Event Button mit 5s Cooldown-Indikator
 */
import { useEffect, useState, useRef, useCallback } from 'react';

const SPEED_STEPS = [0.5, 1, 2, 4];

/**
 * @param {boolean}  running
 * @param {number}   speed
 * @param {Function} onToggle
 * @param {Function} onSpeedChange  (s: number) => void
 * @param {Function} onRandomEvent
 */
export default function Toolbar({ running, speed, onToggle, onSpeedChange, onRandomEvent }) {
  const [cooldown, setCooldown]   = useState(0);   // remaining seconds
  const intervalRef               = useRef(null);

  // ── Space shortcut ──────────────────────────────────────────────────────
  useEffect(() => {
    function onKey(e) {
      if (
        e.code === 'Space' &&
        e.target.tagName !== 'INPUT' &&
        e.target.tagName !== 'SELECT' &&
        e.target.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        onToggle();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onToggle]);

  // ── Random event with cooldown ──────────────────────────────────────────
  const handleRandom = useCallback(() => {
    if (cooldown > 0) return;
    onRandomEvent?.();
    setCooldown(5);
    clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(intervalRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [cooldown, onRandomEvent]);

  // cleanup on unmount
  useEffect(() => () => clearInterval(intervalRef.current), []);

  const hasCooldown = cooldown > 0;

  return (
    <div className="toolbar">
      {/* Brand */}
      <span className="toolbar-title">agent-office</span>

      <div className="toolbar-divider" />

      {/* Play / Pause */}
      <button
        className={`toolbar-btn toolbar-btn--play${running ? ' active' : ''}`}
        onClick={onToggle}
        title="Play / Pause [Space]"
        aria-pressed={running}
      >
        <span className="toolbar-btn-icon">{running ? '⏸' : '▶'}</span>
        {running ? 'Pause' : 'Play'}
        <kbd className="toolbar-kbd">Space</kbd>
      </button>

      {/* Speed selector */}
      <div className="toolbar-speed" role="group" aria-label="Simulationsgeschwindigkeit">
        {SPEED_STEPS.map((s) => (
          <button
            key={s}
            className={`toolbar-speed-btn${speed === s ? ' active' : ''}`}
            onClick={() => onSpeedChange(s)}
            aria-pressed={speed === s}
          >
            {s}×
          </button>
        ))}
      </div>

      <div className="toolbar-divider" />

      {/* Random event */}
      <button
        className={`toolbar-btn toolbar-btn--random${hasCooldown ? ' cooldown' : ''}`}
        onClick={handleRandom}
        disabled={hasCooldown}
        title="Zufalls-Event auslösen"
        aria-disabled={hasCooldown}
      >
        <span className="toolbar-btn-icon">⚡</span>
        Zufall

        {/* Cooldown bar + counter */}
        {hasCooldown && (
          <span className="toolbar-cooldown-wrap" aria-hidden="true">
            <span
              className="toolbar-cooldown-bar"
              style={{ width: `${(cooldown / 5) * 100}%` }}
            />
            <span className="toolbar-cooldown-label">{cooldown}s</span>
          </span>
        )}
      </button>
    </div>
  );
}
