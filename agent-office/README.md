# agent-office

An isometric AI office simulation built with React + Vite.
Five engineering agents work, meet, take coffee breaks, and fetch documents — all driven by an A\* pathfinding engine and a finite state machine.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  agent-office  ⏸ Pause [Space]  0.5× 1× 2× 4×  ⚡ Zufall  ⊡ Fit  📷 Shot  │
├──────────────────────────────────────────────────────────────────────────────┤
│  ARIA ● ARBEIT  │  BRIX ● LÄUFT  │  CADE ● KAFFEE  │  …                    │
├────────────────────────────────────────┬─────────────────────────────────────┤
│                                        │  Szenario ▼                         │
│          isometric SVG scene           │  ──────────────────────             │
│          (pan + zoom)                  │  Event Log                          │
│                                        │  08:14:22 ARIA → Archiv            │
└────────────────────────────────────────┴─────────────────────────────────────┘
│  Agent klicken → auswählen  │  Tile klicken → bewegen  │  Drag → kamera  │  Scroll → zoom  │
```

## Setup

```bash
cd agent-office
npm install
npm run dev
```

Open `http://localhost:5173`.

## Keyboard Shortcuts & Controls

| Key / Action           | Effect                           |
|------------------------|----------------------------------|
| `Space`                | Play / Pause simulation          |
| Mouse drag on scene    | Pan the camera                   |
| Scroll wheel on scene  | Zoom in / out (0.6× – 1.8×)     |
| Click agent card       | Select / deselect agent          |
| Click tile (selected)  | Move selected agent to that tile |
| ⊡ **Fit**             | Reset camera to default position |
| 📷 **Shot**            | Save scene as PNG screenshot     |
| ☀ / 🌙               | Toggle Light / Dark mode         |
| ⚡ **Zufall**          | Trigger a random office event    |
| 0.5× / 1× / 2× / 4×   | Simulation speed multiplier      |

## Agents

| Name | Role           | Color  |
|------|----------------|--------|
| ARIA | Statikerin     | Red    |
| BRIX | CAD-Zeichner   | Orange |
| CADE | FEM-Ingenieur  | Green  |
| DORN | Bauleiter      | Blue   |
| ELSA | Projektleitung | Purple |

## Scenarios

Select via the **Szenario** dropdown in the sidebar. Each scenario runs automatically; use **⏸ Anhalten** to pause mid-scenario.

### 1 · Brücke B42 — Statikprüfung  *(10 Schritte)*
A bridge statics review. ARIA fetches load tables from the archive, BRIX opens CAD drawings on his monitor, the team gathers for a technical meeting, CADE runs a FEM analysis, and ELSA signs off.

### 2 · Notfall: Stütze gerissen  *(8 Schritte)*
Emergency scenario. DORN rushes to the cabinet for inspection reports while ELSA and ARIA hold a crisis meeting. CADE performs a rapid FEM check, and sign-off is expedited over coffee.

### 3 · Baugenehmigung — Unterlagen einreichen  *(9 Schritte)*
Permit submission workflow. ELSA coordinates while each agent retrieves their specialist documents. A final review meeting and a coffee break precede the sign-off.

### 4 · DIN-Norm Update  *(7 Schritte)*
All five agents review a new engineering standard at their desks, discuss implications in a group meeting, and update their calculation templates simultaneously.

## Architecture

```
src/
├── agents/
│   └── agentMachine.js      State machine + tick(), startWalk(), applySpeech()
├── data/
│   ├── constants.js          TILE_W=64, TILE_H=32, ORIGIN_X/Y, GRID_COLS/ROWS …
│   ├── officeLayout.js       WALLS, DESKS, MEETING_TABLE, OFFICE_OBSTACLES (Set)
│   └── scenarios.js          STARTUP_AGENTS + 4 scenario definitions
├── engine/
│   ├── iso.js                iso(), screenToGrid(), sortByDepth()
│   └── pathfinding.js        A* with MinHeap, diagonal corner-cutting blocked
├── hooks/
│   ├── useAgentLoop.js       rAF-driven simulation loop, speed/pause via refs
│   └── useScenario.js        Step sequencer with two-phase completion guard
├── scene/
│   ├── Agent.jsx             Pixel-art SVG sprites, 4-frame walk animation
│   ├── Furniture.jsx         React.memo'd isometric furniture components
│   └── Scene.jsx             SVG canvas, camera pan/zoom, forwardRef API
└── ui/
    ├── AgentStatusBar.jsx    Pulsing status cards with scroll overflow
    ├── EventLog.jsx          Scrollable event log with slide-in animation
    ├── ScenarioPanel.jsx     Dropdown, progress bar, next-step preview
    └── Toolbar.jsx           Play/pause, speed, random event, camera, theme
```

### Key design decisions

- **No external dependencies** beyond Vite + React (screenshot uses native `XMLSerializer` + Canvas API)
- **Painter's Algorithm** (`sortByDepth`) for correct isometric overlap — runs O(n log n) per frame on ~50 items
- **Two-phase scenario completion**: waits for agents to leave IDLE before checking for return-to-IDLE, preventing races with React state lag
- **React.memo on furniture** with primitive props prevents re-renders on every animation frame
- **Camera pan/zoom** implemented via an SVG `<g transform="translate(x,y) scale(z)">` wrapper; wheel listener registered non-passively to allow `preventDefault()`

## License

MIT
