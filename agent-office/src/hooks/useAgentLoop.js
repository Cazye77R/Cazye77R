import { useEffect, useRef } from 'react';
import { TICK_MS } from '../data/constants';

// Drives the simulation tick for all agents
export function useAgentLoop(running, speed, onTick) {
  const tickRef = useRef(null);

  useEffect(() => {
    if (!running) {
      clearInterval(tickRef.current);
      return;
    }
    tickRef.current = setInterval(() => {
      onTick();
    }, TICK_MS / speed);
    return () => clearInterval(tickRef.current);
  }, [running, speed, onTick]);
}
