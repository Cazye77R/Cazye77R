/**
 * ScenarioPanel.jsx
 * Zeigt aktives Szenario, Fortschrittsbalken, Next-Step-Preview
 * und ein Dropdown zur Szenario-Auswahl.
 */
import { SCENARIO_LIST } from '../data/scenarios';

// ---------------------------------------------------------------------------
// Next-step label generator
// ---------------------------------------------------------------------------

function nextStepLabel(scenario, stepIdx) {
  if (!scenario) return null;
  const s = scenario.steps[stepIdx + 1];
  if (!s) return null;

  switch (s.type) {
    case 'work':
      return `${s.agent?.toUpperCase()} → Schreibtisch`;
    case 'cabinet':
      return `${s.agent?.toUpperCase()} → Archiv`;
    case 'coffee':
      return `${s.agent?.toUpperCase()} → Kaffee`;
    case 'meet':
      return `Meeting: „${s.topic}"`;
    case 'parallel': {
      const names = s.steps
        .map((sub) => sub.agent?.toUpperCase() ?? sub.agents?.map((id) => id.toUpperCase()).join('+'))
        .filter(Boolean)
        .join(' + ');
      return `${names} parallel`;
    }
    default:
      return s.type;
  }
}

// ---------------------------------------------------------------------------
// Current-step summary
// ---------------------------------------------------------------------------

function currentStepSummary(step) {
  if (!step) return null;
  switch (step.type) {
    case 'work':    return `${step.agent?.toUpperCase()} arbeitet`;
    case 'cabinet': return `${step.agent?.toUpperCase()} → Archiv`;
    case 'coffee':  return `${step.agent?.toUpperCase()} → Kaffee`;
    case 'meet':    return `Meeting: „${step.topic}"`;
    case 'parallel': {
      const count = step.steps?.length ?? 0;
      return `${count} parallele Aufgaben`;
    }
    default: return step.type;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * @param {object}   props
 * @param {string}   props.scenarioId
 * @param {object}   props.scenario
 * @param {object}   props.currentStep
 * @param {number}   props.stepIdx
 * @param {number}   props.totalSteps
 * @param {number}   props.progress      0..1
 * @param {boolean}  props.paused
 * @param {boolean}  props.done
 * @param {Function} props.onStart       (id) => void
 * @param {Function} props.onPause
 * @param {Function} props.onResume
 * @param {Function} props.onReset
 */
export default function ScenarioPanel({
  scenarioId,
  scenario,
  currentStep,
  stepIdx,
  totalSteps,
  progress,
  paused,
  done,
  onStart,
  onPause,
  onResume,
  onReset,
}) {
  const nextLabel    = nextStepLabel(scenario, stepIdx);
  const currentLabel = currentStepSummary(currentStep);
  const isRunning    = !!scenario && !done;

  return (
    <div className="scenario-panel">
      {/* Header */}
      <div className="scenario-panel-header">
        <span className="section-title">Szenario</span>
        {scenario && (
          <button className="scenario-reset-btn" onClick={onReset} title="Zurücksetzen">
            ↺
          </button>
        )}
      </div>

      {/* Dropdown */}
      <select
        className="scenario-select"
        value={scenarioId ?? ''}
        onChange={(e) => { if (e.target.value) onStart(e.target.value); }}
        aria-label="Szenario auswählen"
      >
        <option value="">— Szenario wählen —</option>
        {SCENARIO_LIST.map((sc) => (
          <option key={sc.id} value={sc.id}>
            {sc.icon}  {sc.name}
          </option>
        ))}
      </select>

      {/* Active scenario details */}
      {scenario && (
        <div className="scenario-body">
          {/* Title + description */}
          <div className="scenario-meta">
            <span className="scenario-icon" aria-hidden="true">{scenario.icon}</span>
            <div className="scenario-meta-text">
              <div className="scenario-name" style={{ color: scenario.color }}>
                {scenario.name}
              </div>
              <div className="scenario-desc">{scenario.description}</div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="scenario-progress-wrap">
            <div className="scenario-progress-track">
              <div
                className="scenario-progress-fill"
                style={{ width: `${progress * 100}%`, background: scenario.color }}
              />
            </div>
            <span className="scenario-step-count">
              {done
                ? '✓'
                : stepIdx >= 0
                  ? `${stepIdx + 1}/${totalSteps}`
                  : '–'}
            </span>
          </div>

          {/* Current step */}
          {currentLabel && !done && (
            <div className="scenario-current">
              <span className="scenario-label-pill">Jetzt</span>
              <span className="scenario-current-text">{currentLabel}</span>
            </div>
          )}

          {/* Next step preview */}
          {nextLabel && !done && (
            <div className="scenario-next">
              <span className="scenario-label-pill scenario-label-pill--dim">Dann</span>
              <span className="scenario-next-text">{nextLabel}</span>
            </div>
          )}

          {/* Done banner */}
          {done && (
            <div className="scenario-done-banner">✓ Abgeschlossen</div>
          )}

          {/* Pause / Resume */}
          {isRunning && (
            <button
              className={`scenario-ctrl-btn${paused ? ' scenario-ctrl-btn--paused' : ''}`}
              onClick={paused ? onResume : onPause}
            >
              {paused ? '▶ Fortsetzen' : '⏸ Anhalten'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
