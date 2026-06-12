/**
 * Toolbar.jsx
 * Globale Steuerleiste:
 *  - Play/Pause mit [Space]-Shortcut
 *  - Geschwindigkeit: 0.5x / 1x / 2x / 4x
 *  - Zufalls-Event Button mit 5s Cooldown-Indikator
 *  - Kamera-Fit / Screenshot / Dark-Light-Toggle
 */
import { useEffect, useState, useRef, useCallback } from 'react';

const SPEED_STEPS = [0.5, 1, 2, 4];

export default function Toolbar({
  running,
  speed,
  darkMode,
  onToggle,
  onSpeedChange,
  onRandomEvent,
  onToggleTheme,
  onFitScreen,
  onScreenshot,
}) {
  const [cooldown, setCooldown] = useState(0);
  const intervalRef = useRef(null);

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
        if (prev <= 1) { clearInterval(intervalRef.current); return 0; }
        return prev - 1;
      });
    }, 1000);
  }, [cooldown, onRandomEvent]);

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

      <div className="toolbar-divider" />

      {/* Fit to screen */}
      <button
        className="toolbar-btn"
        onClick={onFitScreen}
        title="Kamera auf Standardposition zurücksetzen"
      >
        <span className="toolbar-btn-icon">⊡</span>
        Fit
      </button>

      {/* Screenshot */}
      <button
        className="toolbar-btn"
        onClick={onScreenshot}
        title="Screenshot als PNG speichern"
      >
        <span className="toolbar-btn-icon">📷</span>
        Shot
      </button>

      {/* Dark / Light toggle — pushed to right edge */}
      <button
        className={`toolbar-btn toolbar-btn--theme${darkMode ? '' : ' active'}`}
        onClick={onToggleTheme}
        title={darkMode ? 'Zu Light Mode wechseln' : 'Zu Dark Mode wechseln'}
        style={{ marginLeft: 'auto' }}
      >
        <span className="toolbar-btn-icon">{darkMode ? '☀' : '🌙'}</span>
        {darkMode ? 'Light' : 'Dark'}
      </button>
    </div>
  );
}
