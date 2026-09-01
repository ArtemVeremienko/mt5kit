import { Component, For, Show } from 'solid-js';
import { positionsStore } from '../../stores/positionsStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { PositionRow } from './PositionRow';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';

export const OrderManagementPanel: Component = () => {
  const positions = positionsStore.positions;
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
      <div class="table-card">
        <div class="table-responsive">
          <table class="positions-table">
            <thead>
              <tr>
                <th class="text-left" style={{ width: '100px' }}>Ticket</th>
                <th class="text-left" style={{ width: '160px' }}>Symbol / Type</th>
                <th class="text-right" style={{ width: '120px' }}>Volume</th>
                <th class="text-right" style={{ width: '110px' }}>Open Price</th>
                <th class="text-right" style={{ width: '110px' }}>Current Price</th>
                <th class="text-right" style={{ 'min-width': '175px' }}>Floating P&L</th>
                <th class="text-center" style={{ width: '115px' }}>R-Multiple</th>
                <th class="text-center" style={{ 'min-width': '160px' }}>Stop Loss / Take Profit</th>
                <th class="text-right" style={{ 'min-width': '170px' }}>
                  <div class="th-actions-header">
                    <span>Actions</span>
                    <Show when={count() > 0}>
                      <button
                        type="button"
                        class="btn-emergency-close-compact"
                        onClick={handleCloseAll}
                        disabled={positionsStore.isActionInProgress()}
                        title="Parallel emergency liquidation of all open trades"
                      >
                        🛑 Close All ({count()})
                      </button>
                    </Show>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              <Show
                when={positions().length > 0}
                fallback={
                  <tr>
                    <td colspan="9" class="empty-table-cell">
                      <div class="empty-state-card">
                        <span class="empty-state-icon">💼</span>
                        <div class="empty-state-title">No Open Positions Active</div>
                        <div class="empty-state-desc">
                          Your MT5 account currently has zero open market exposure. Use the Market Screener to size and execute a position.
                        </div>
                        <button
                          type="button"
                          class="btn-reset-filters-hero"
                          onClick={() => preferencesStore.setActiveView('matrix')}
                        >
                          🎯 Switch to Risk Screener (Hotkey: 1)
                        </button>
                      </div>
                    </td>
                  </tr>
                }
              >
                <For each={positionsStore.positionTickets()}>
                  {(ticket) => <PositionRow ticket={ticket} />}
                </For>
              </Show>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
