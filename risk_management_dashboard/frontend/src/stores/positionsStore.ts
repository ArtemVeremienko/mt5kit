import { createSignal, createRoot, createMemo } from 'solid-js';
import { OpenPosition } from '../types';

function createPositionsStore() {
  const [positions, setPositions] = createSignal<OpenPosition[]>([]);
  const [isActionInProgress, setIsActionInProgress] = createSignal<boolean>(false);

  const totalFloatingProfit = createMemo(() => {
    return positions().reduce((acc, p) => acc + (p.profit || 0), 0);
  });

  const totalPositionsCount = createMemo(() => positions().length);

  return {
    positions,
    setPositions,
    totalFloatingProfit,
    totalPositionsCount,
    isActionInProgress,
    setIsActionInProgress,
  };
}

export const positionsStore = createRoot(createPositionsStore);
