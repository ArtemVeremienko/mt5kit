import { Component, For, Show } from 'solid-js';
import { positionsStore } from '../../stores/positionsStore';
import { PositionRow } from './PositionRow';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';
import { formatCurrency } from '../../utils/formatters';

export const OrderManagementPanel: Component = () => {
  const positions = positionsStore.positions;
  const totalProfit = positionsStore.totalFloatingProfit;
  const count = positionsStore.totalPositionsCount;

  const handleCloseAll = async () => {
    if (!window.confirm(`Are you sure you want to close ALL ${count()} open positions immediately?`)) {
      return;
    }

    try {
      positionsStore.setIsActionInProgress(true);
      const res = await api.closeAllPositions();
      toastStore.addToast(
        'Emergency Liquidation Executed',
        `Closed ${res.count} positions across terminal`,
        'warning'
      );
    } catch (e: any) {
      toastStore.addToast('Error', e.message || 'Failed to close all positions', 'error');
    } finally {
      positionsStore.setIsActionInProgress(false);
    }
  };

  return (
    <div class="positions-section">
      <div class="positions-header">
        <div class="positions-title-group">
          <span class="panel-icon">💼</span>
          <h2 class="panel-title">LIVE OPEN POSITIONS</h2>
          <span class="pos-count-badge">{count()} Active</span>
          <Show when={count() > 0}>
            <span
              class="pos-total-pnl-pill"
              classList={{
                'text-profit': totalProfit() > 0,
                'text-loss': totalProfit() < 0,
              }}
            >
              Total P&L: {totalProfit() >= 0 ? `+${formatCurrency(totalProfit())}` : formatCurrency(totalProfit())}
            </span>
          </Show>
        </div>

        <div class="positions-actions">
          <Show when={count() > 0}>
            <button
              class="btn-emergency-close"
              onClick={handleCloseAll}
              disabled={positionsStore.isActionInProgress()}
              title="Parallel emergency liquidation of all open trades"
            >
              🛑 Emergency Close All ({count()})
            </button>
          </Show>
        </div>
      </div>

      <div class="table-card">
        <div class="table-responsive">
          <table class="positions-table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Symbol / Type</th>
                <th>Volume</th>
                <th>Open Price</th>
                <th>Current Price</th>
                <th>Floating P&L</th>
                <th>R-Multiple</th>
                <th>Stop Loss / Take Profit</th>
                <th class="text-center" style={{ 'min-width': '180px' }}>
                  Position Actions
                </th>
              </tr>
            </thead>
            <tbody>
              <Show
                when={positions().length > 0}
                fallback={
                  <tr>
                    <td colspan="9" class="empty-table-msg">
                      No open positions currently active in MT5 terminal.
                    </td>
                  </tr>
                }
              >
                <For each={positions()}>
                  {(pos) => <PositionRow position={pos} />}
                </For>
              </Show>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
