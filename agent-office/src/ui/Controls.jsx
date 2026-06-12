// Simulation controls (play/pause/speed)
export default function Controls({ running, speed, onToggle, onSpeedChange }) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: 8 }}>
      <button onClick={onToggle}>{running ? 'Pause' : 'Play'}</button>
      <label>
        Speed:
        <input
          type="range"
          min={1}
          max={10}
          value={speed}
          onChange={(e) => onSpeedChange(Number(e.target.value))}
        />
        {speed}x
      </label>
    </div>
  );
}
