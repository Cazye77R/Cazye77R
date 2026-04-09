import { useState } from 'react';
import { SCENARIOS } from '../data/scenarios';

// Loads and manages scenario state
export function useScenario(scenarioId = 'startup') {
  const scenario = SCENARIOS[scenarioId];
  const [agents, setAgents] = useState(scenario.agents);
  const [log, setLog] = useState([]);

  function logEvent(agentId, message) {
    const time = new Date().toLocaleTimeString();
    setLog((prev) => [...prev.slice(-99), { time, agent: agentId, message }]);
  }

  return { scenario, agents, setAgents, log, logEvent };
}
