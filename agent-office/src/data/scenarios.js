import { createAgentMachine } from '../agents/agentMachine';

/**
 * Startup-Szenario: 5 Agents, Heimatpositionen entsprechen den
 * Schreibtisch-Positionen aus officeLayout.js (DESKS).
 * Namen entsprechen AGENT_STYLES in scene/Agent.jsx.
 */
export const STARTUP_AGENTS = [
  createAgentMachine('aria', 'ARIA', 'Engineer',  1, 2),
  createAgentMachine('brix', 'BRIX', 'Designer',  3, 2),
  createAgentMachine('cade', 'CADE', 'Developer', 6, 2),
  createAgentMachine('dorn', 'DORN', 'DevOps',    8, 2),
  createAgentMachine('elsa', 'ELSA', 'Manager',   1, 6),
];

// Legacy-Export (useScenario.js)
export const SCENARIOS = {
  startup: {
    id: 'startup',
    label: 'Startup Office',
    gridSize: { cols: 11, rows: 9 },
    agents: STARTUP_AGENTS,
  },
};
