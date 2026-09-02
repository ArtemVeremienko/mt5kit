import { Component, For, Show, createSignal, onCleanup } from 'solid-js';
import { positionsStore } from '../../stores/positionsStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { PositionRow } from './PositionRow';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';

export const OrderManagementPanel: Component = () => {
  const positions = positionsStore.positions;
  const count = positionsStore.totalPositionsCount;
  const [isArmedCloseAll, setIsArmedCloseAll] = createSignal<boolean>(false);
  let armedTimer: any;

  const handleCloseAllClick = async () => {
    if (!isArmedCloseAll()) {
      setIsArmedCloseAll(true);
      clearTimeout(armedTimer);
      armedTimer = setTimeout(() => {
        setIsArmedCloseAll(false);
      }, 4000); // 4-second safety window
      return;
    }

    clearTimeout(armedTimer);
    setIsArmedCloseAll(false);

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

  onCleanup(() => {
    clearTimeout(armedTimer);
  });

  return (
    <div class="positions-section">
      <div class="table-card">
        <div class="table-responsive">
          <table class="positions-table">
            <thead>
              <tr>
                <th class="text-left col-th-ticket">Ticket</th>
                <th class="text-left col-th-symbol">Symbol / Type</th>
                <th class="text-right col-th-volume">Volume</th>
                <th class="text-right col-th-open">Open Price</th>
                <th class="text-right col-th-current">Current Price</th>
                <th class="text-center col-th-sl">Stop Loss</th>
                <th class="text-center col-th-tp">Take Profit</th>
                <th class="text-right col-th-pnl">Floating P&L</th>
                <th class="text-center col-th-r">R-Multiple</th>
                <th class="text-right col-th-actions">
                  <div class="th-actions-header">
                    <span>Actions</span>
                    <Show when={count() > 0}>
                      <button
                        type="button"
                        class="btn-emergency-close-compact"
                        classList={{
                          'btn-armed-critical': isArmedCloseAll(),
                        }}
                        onClick={handleCloseAllClick}
                        disabled={positionsStore.isActionInProgress()}
                        title={
                          isArmedCloseAll()
                            ? 'Click again to CONFIRM parallel emergency liquidation'
                            : 'Parallel emergency liquidation of all open trades (2-step safety)'
                        }
                      >
                        {isArmedCloseAll()
                          ? `⚠️ Confirm Close ALL (${count()})`
                          : `🛑 Close All (${count()})`}
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
                    <td colspan="10" class="empty-table-cell">
                      <div class="empty-state-card">
                        <span class="empty-state-icon">💼</span>
                        <div class="empty-state-title">No Open Positions Active</div>
                        <div class="empty-state-desc">
                          Your MT5 account currently has zero open market exposure. Use the Risk Matrix to size and execute a position.
                        </div>
                        <button
                          type="button"
                          class="btn-reset-filters-hero"
                          onClick={() => preferencesStore.setActiveView('matrix')}
                        >
                          🎯 Switch to Risk Matrix (Hotkey: 1)
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

