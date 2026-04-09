// Agent factory and state helpers

export function createAgent(id, name, role, position) {
  return {
    id,
    name,
    role,
    position, // { col, row }
    state: 'idle', // idle | working | moving | thinking
    task: null,
    log: [],
  };
}

export function updateAgentState(agent, patch) {
  return { ...agent, ...patch };
}
