import { createSignal, createRoot, createMemo } from 'solid-js';
import { OpenPosition } from '../types';

function createPositionsStore() {
  const [positions, setPositions] = createSignal<OpenPosition[]>([]);
  const [isActionInProgress, setIsActionInProgress] = createSignal<boolean>(false);

  const positionsMap = createMemo<Map<number, OpenPosition>>(() => {
    const map = new Map<number, OpenPosition>();
    for (const p of positions()) {
      map.set(p.ticket, p);
    }
    return map;
  });

  const positionTickets = createMemo<number[]>(() => {
    return positions().map((p) => p.ticket);
  });

  const getPosition = (ticket: number): OpenPosition | undefined => {
    return positionsMap().get(ticket);
  };

  const totalFloatingProfit = createMemo(() => {
    return positions().reduce((acc, p) => acc + (p.profit || 0), 0);
  });

  const totalPositionsCount = createMemo(() => positions().length);

  return {
    positions,
    setPositions,
    positionsMap,
    positionTickets,
    getPosition,
    totalFloatingProfit,
    totalPositionsCount,
    isActionInProgress,
    setIsActionInProgress,
  };
}

export const positionsStore = createRoot(createPositionsStore);
