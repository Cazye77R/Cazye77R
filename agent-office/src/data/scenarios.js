// Predefined office scenarios
export const SCENARIOS = {
  startup: {
    id: 'startup',
    label: 'Startup Office',
    gridSize: { cols: 10, rows: 10 },
    agents: [
      { id: 'a1', name: 'Alice', role: 'Engineer', position: { col: 2, row: 2 } },
      { id: 'a2', name: 'Bob', role: 'Designer', position: { col: 5, row: 3 } },
      { id: 'a3', name: 'Charlie', role: 'Manager', position: { col: 7, row: 6 } },
    ],
  },
};
