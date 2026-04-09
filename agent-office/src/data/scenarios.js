/**
 * scenarios.js
 *
 * Agenten-Stammdaten und 4 vollständige Szenarien für das isometrische
 * Ingenieurbüro. Jedes Szenario besteht aus einem geordneten steps[]-Array.
 *
 * Step-Typen
 * ──────────
 * { type:'work',     agent, message, duration }
 *   → Agent geht zum eigenen Schreibtisch, arbeitet, kehrt zurück
 *
 * { type:'cabinet',  agent, message, duration }
 *   → Agent geht zum Aktenschrank, kehrt zurück
 *
 * { type:'coffee',   agent, duration }
 *   → Agent geht zur Kaffeemaschine, kehrt zurück
 *
 * { type:'meet',     agents[], topic, speeches:{agentId:text}, duration }
 *   → Mehrere Agents gehen zum Besprechungstisch, kehren zurück
 *
 * { type:'parallel', steps[] }
 *   → Alle Sub-Steps gleichzeitig; nächster Step startet wenn ALLE fertig
 */

import { createAgentMachine } from '../agents/agentMachine';

// ---------------------------------------------------------------------------
// Agents (Rollen passen zum Ingenieurbüro-Kontext)
// ---------------------------------------------------------------------------

export const STARTUP_AGENTS = [
  createAgentMachine('aria', 'ARIA', 'Statikerin',     1, 2),
  createAgentMachine('brix', 'BRIX', 'CAD-Zeichner',   3, 2),
  createAgentMachine('cade', 'CADE', 'FEM-Ingenieur',  6, 2),
  createAgentMachine('dorn', 'DORN', 'Bauleiter',      8, 2),
  createAgentMachine('elsa', 'ELSA', 'Projektleitung', 1, 6),
];

// ---------------------------------------------------------------------------
// Szenario 1 — Brückenplanung B42
// ---------------------------------------------------------------------------

const BRUECKE_B42 = {
  id: 'bruecke-b42',
  name: 'Brückenplanung B42',
  icon: '🌉',
  color: '#1565c0',
  description:
    'Statik und Tragwerksplanung für die neue Autobahnbrücke B42 ' +
    'über den Rinbach – von der Lastannahme bis zur Ausführungsfreigabe.',
  steps: [
    {
      type: 'work',
      agent: 'elsa',
      message: 'Projektauftrag prüfen...',
      duration: 3500,
    },
    {
      type: 'meet',
      agents: ['elsa', 'aria', 'brix'],
      topic: 'Kickoff B42',
      speeches: {
        elsa: 'Stützweite 60 m!',
        aria: 'Lastklasse SLW 60.',
        brix: 'Lageplan folgt.',
      },
      duration: 7000,
    },
    {
      type: 'parallel',
      steps: [
        { type: 'work',    agent: 'aria', message: 'Lastannahmen berechnen...', duration: 5000 },
        { type: 'work',    agent: 'brix', message: 'Lageplan zeichnen...', duration: 5000 },
        { type: 'cabinet', agent: 'dorn', message: 'Bestandspläne holen...', duration: 3500 },
      ],
    },
    {
      type: 'work',
      agent: 'cade',
      message: 'FEM-Modell aufbauen...',
      duration: 5500,
    },
    {
      type: 'cabinet',
      agent: 'aria',
      message: 'DIN 1045 nachlesen...',
      duration: 3000,
    },
    {
      type: 'meet',
      agents: ['aria', 'cade'],
      topic: 'Statikbesprechung',
      speeches: {
        aria: 'Biegemoment kritisch!',
        cade: 'Simulation läuft...',
      },
      duration: 6000,
    },
    {
      type: 'coffee',
      agent: 'brix',
      duration: 2500,
    },
    {
      type: 'parallel',
      steps: [
        { type: 'work', agent: 'aria', message: 'Bewehrung optimieren...', duration: 4500 },
        { type: 'work', agent: 'dorn', message: 'Ausschreibung vorbereiten...', duration: 4500 },
      ],
    },
    {
      type: 'meet',
      agents: ['aria', 'brix', 'cade', 'dorn', 'elsa'],
      topic: 'Abschluss-Review',
      speeches: {
        elsa: 'Alle Prüfpunkte ok?',
        aria: 'Statik freigegeben.',
        dorn: 'Termin gehalten!',
      },
      duration: 8000,
    },
    {
      type: 'work',
      agent: 'elsa',
      message: 'Abschlussbericht schreiben...',
      duration: 4000,
    },
  ],
};

// ---------------------------------------------------------------------------
// Szenario 2 — Notfall: Rissbildung Stütze 7
// ---------------------------------------------------------------------------

const NOTFALL_STUETZE = {
  id: 'notfall-stuetze',
  name: 'Notfall: Rissbildung Stütze 7',
  icon: '⚠️',
  color: '#b71c1c',
  description:
    'Kritische Rissbildung an Stütze 7 entdeckt – sofortige Neuberechnung, ' +
    'Krisenrunde und Einleitung von Sicherungsmaßnahmen.',
  steps: [
    {
      type: 'work',
      agent: 'dorn',
      message: 'Riss entdeckt! Fotos gemacht.',
      duration: 2500,
    },
    {
      type: 'meet',
      agents: ['elsa', 'aria'],
      topic: 'NOTFALL-Besprechung',
      speeches: {
        elsa: 'Sofortmaßnahmen!',
        aria: 'Ich brauche die Statik!',
      },
      duration: 5000,
    },
    {
      type: 'cabinet',
      agent: 'aria',
      message: 'Originalstatik Stütze 7!',
      duration: 4000,
    },
    {
      type: 'work',
      agent: 'cade',
      message: 'Notfall-FEM gestartet...',
      duration: 6000,
    },
    {
      type: 'parallel',
      steps: [
        { type: 'work', agent: 'aria', message: 'Traglast neu berechnen...', duration: 5000 },
        { type: 'work', agent: 'brix', message: 'Rissplan zeichnen...', duration: 5000 },
      ],
    },
    {
      type: 'meet',
      agents: ['elsa', 'aria', 'cade', 'dorn'],
      topic: 'Krisenrunde',
      speeches: {
        aria: 'Traglast reduziert!',
        cade: 'FEM: Versagen in 48h.',
        elsa: 'Sperrung anordnen!',
        dorn: 'Absperrung läuft.',
      },
      duration: 9000,
    },
    {
      type: 'parallel',
      steps: [
        { type: 'work', agent: 'dorn', message: 'Sofortsicherung koordinieren...', duration: 5000 },
        { type: 'work', agent: 'aria', message: 'Verstärkungsnachweis erstellen...', duration: 5000 },
      ],
    },
    {
      type: 'work',
      agent: 'elsa',
      message: 'Schadensbericht → Behörde...',
      duration: 4000,
    },
  ],
};

// ---------------------------------------------------------------------------
// Szenario 3 — Baugenehmigung Antrag
// ---------------------------------------------------------------------------

const BAUGENEHMIGUNG = {
  id: 'baugenehmigung',
  name: 'Baugenehmigung Antrag',
  icon: '📋',
  color: '#e65100',
  description:
    'Vollständige Antragsunterlagen für die Baugenehmigung des Industriekomplexes Nord – ' +
    'Statiknachweis, Bauzeichnungen und Behördenkoordination.',
  steps: [
    {
      type: 'meet',
      agents: ['elsa', 'brix'],
      topic: 'Antrag-Vorbereitung',
      speeches: {
        elsa: 'Abgabe in 2 Wochen!',
        brix: 'Welche Pläne fehlen?',
      },
      duration: 5500,
    },
    {
      type: 'cabinet',
      agent: 'brix',
      message: 'Formularvorlagen holen...',
      duration: 3000,
    },
    {
      type: 'work',
      agent: 'aria',
      message: 'Statiknachweis DIN 1054...',
      duration: 5500,
    },
    {
      type: 'cabinet',
      agent: 'dorn',
      message: 'Bestandspläne suchen...',
      duration: 4000,
    },
    {
      type: 'work',
      agent: 'brix',
      message: 'Grundrisse & Ansichten...',
      duration: 6000,
    },
    {
      type: 'cabinet',
      agent: 'aria',
      message: 'Brandschutz-Normen prüfen...',
      duration: 3500,
    },
    {
      type: 'parallel',
      steps: [
        { type: 'work', agent: 'cade', message: 'Unterlagen digitalisieren...', duration: 4500 },
        { type: 'work', agent: 'dorn', message: 'Behördenliste koordinieren...', duration: 4500 },
      ],
    },
    {
      type: 'meet',
      agents: ['elsa', 'aria'],
      topic: 'Abnahme-Review',
      speeches: {
        elsa: 'Alles vollständig?',
        aria: 'Statik freigegeben.',
      },
      duration: 5000,
    },
    {
      type: 'work',
      agent: 'dorn',
      message: 'Einreichen – Amt 63...',
      duration: 4500,
    },
  ],
};

// ---------------------------------------------------------------------------
// Szenario 4 — DIN-Norm Update Review
// ---------------------------------------------------------------------------

const DIN_UPDATE = {
  id: 'din-update',
  name: 'DIN-Norm Update Review',
  icon: '📐',
  color: '#1b5e20',
  description:
    'Überprüfung aller betroffenen Statiken nach Aktualisierung der ' +
    'DIN EN 1992-1-1 – CAD-Vorlagen, FEM-Skripte und Bestandspläne.',
  steps: [
    {
      type: 'meet',
      agents: ['aria', 'brix'],
      topic: 'Norm-Einführung',
      speeches: {
        aria: 'DIN EN 1992 geändert!',
        brix: 'CAD-Vorlagen anpassen?',
      },
      duration: 5000,
    },
    {
      type: 'cabinet',
      agent: 'aria',
      message: 'Alte DIN-Ausgabe holen...',
      duration: 3500,
    },
    {
      type: 'parallel',
      steps: [
        { type: 'work', agent: 'aria', message: 'Δ-Änderungen §6.1 prüfen...', duration: 5000 },
        { type: 'work', agent: 'cade', message: 'FEM-Skripte auf neue Norm...', duration: 5000 },
      ],
    },
    {
      type: 'work',
      agent: 'brix',
      message: 'CAD-Titelblöcke aktualisieren...',
      duration: 4000,
    },
    {
      type: 'parallel',
      steps: [
        { type: 'work', agent: 'cade', message: 'Vergleichsrechnung läuft...', duration: 5500 },
        { type: 'work', agent: 'aria', message: 'Decke B12 prüfen...',         duration: 5500 },
      ],
    },
    {
      type: 'cabinet',
      agent: 'dorn',
      message: 'Betroffene Pläne suchen...',
      duration: 4000,
    },
    {
      type: 'meet',
      agents: ['aria', 'brix', 'cade', 'dorn', 'elsa'],
      topic: 'DIN-Update Abschluss',
      speeches: {
        aria: '14 Statiken betroffen.',
        cade: 'Alle FEM-Modelle ok.',
        elsa: 'Dokumentation einfrieren.',
      },
      duration: 8000,
    },
  ],
};

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

/** Lookup-Map für useScenarioRunner */
export const SCENARIOS = {
  [BRUECKE_B42.id]:    BRUECKE_B42,
  [NOTFALL_STUETZE.id]: NOTFALL_STUETZE,
  [BAUGENEHMIGUNG.id]: BAUGENEHMIGUNG,
  [DIN_UPDATE.id]:     DIN_UPDATE,
};

/** Geordnete Liste für UI-Menüs */
export const SCENARIO_LIST = [BRUECKE_B42, NOTFALL_STUETZE, BAUGENEHMIGUNG, DIN_UPDATE];
