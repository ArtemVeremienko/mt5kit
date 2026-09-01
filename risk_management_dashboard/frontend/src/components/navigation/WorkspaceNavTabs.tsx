import { Component, Show } from 'solid-js';
import { preferencesStore } from '../../stores/preferencesStore';
import { marketStore } from '../../stores/marketStore';
import { positionsStore } from '../../stores/positionsStore';
import { formatCurrency } from '../../utils/formatters';

export const WorkspaceNavTabs: Component = () => {
  const activeView = preferencesStore.activeView;
  const symbolCount = () => marketStore.rawSymbols().length;
  const posCount = positionsStore.totalPositionsCount;
  const totalProfit = positionsStore.totalFloatingProfit;

  return (
    <div class="workspace-nav-container">
      <div class="workspace-segmented-control">
        <button
          class="workspace-tab-btn"
          classList={{ active: activeView() === 'matrix' }}
          onClick={() => preferencesStore.setActiveView('matrix')}
          title="Switch to Market Risk Screener Matrix (Hotkey: 1)"
        >
          <span class="tab-icon">🎯</span>
          <span class="tab-label">RISK MATRIX SCREENER</span>
          <span class="tab-count-pill">{symbolCount()} Symbols</span>
          <span class="tab-hotkey-badge">1</span>
        </button>

        <button
          class="workspace-tab-btn"
          classList={{
            active: activeView() === 'positions',
            'has-open-positions': posCount() > 0,
          }}
          onClick={() => preferencesStore.setActiveView('positions')}
          title="Switch to Live Open Positions Manager (Hotkey: 2)"
        >
          <span class="tab-icon">💼</span>
          <span class="tab-label">LIVE OPEN POSITIONS</span>
          <span
            class="tab-count-pill"
            classList={{
              'pill-active-orders': posCount() > 0,
            }}
          >
            {posCount()} Active
          </span>
          <Show when={posCount() > 0}>
            <span
              class="tab-pnl-pill"
              classList={{
                'text-profit': totalProfit() > 0,
                'text-loss': totalProfit() < 0,
              }}
            >
              {totalProfit() >= 0 ? `+${formatCurrency(totalProfit())}` : formatCurrency(totalProfit())}
            </span>
          </Show>
          <span class="tab-hotkey-badge">2</span>
        </button>
      </div>
    </div>
  );
};
