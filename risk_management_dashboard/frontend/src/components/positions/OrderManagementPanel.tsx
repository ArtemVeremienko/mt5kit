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

  const totalPnl = () => positions().reduce((acc, p) => acc + (p.profit || 0), 0);
  const totalVolume = () => positions().reduce((acc, p) => acc + (p.volume || 0), 0);

  const handleBreakEvenAllClick = async () => {
    try {
      positionsStore.setIsActionInProgress(true);
      const res = await api.breakEvenAllPositions();
      if (res.count_modified > 0) {
        toastStore.addToast(
          'Break-Even Snapped',
          `Protected ${res.count_modified} position(s) with cost-absorbing BE.${res.count_skipped > 0 ? ` Skipped ${res.count_skipped} trade(s) in drawdown.` : ''}`,
          'success'
        );
      } else if (res.count_skipped > 0) {
        toastStore.addToast(
          'No Eligible Positions',
          `Skipped ${res.count_skipped} position(s) because they are in drawdown or cannot yet cover spread & commission fees.`,
          'info'
        );
      } else {
        toastStore.addToast('Break-Even Completed', 'No open positions to modify.', 'info');
      }
    } catch (e: any) {
      toastStore.addToast('Error', e.message || 'Failed to move positions to Break-Even', 'error');
    } finally {
      positionsStore.setIsActionInProgress(false);
    }
  };

  const handleClose50AllClick = async () => {
    try {
      positionsStore.setIsActionInProgress(true);
      const res = await api.close50AllPositions();
      if (res.count_scaled_out > 0 || res.count_be_locked > 0) {
        toastStore.addToast(
          'TP1 Scale-Out & Protect',
          `Scaled out ${res.count_scaled_out} trade(s) and locked BE on ${res.count_be_locked} trade(s).${res.count_skipped > 0 ? ` Skipped ${res.count_skipped} trade(s) in drawdown.` : ''}`,
          'success'
        );
      } else if (res.count_skipped > 0) {
        toastStore.addToast(
          'TP1 Skipped',
          `Skipped ${res.count_skipped} position(s) that are currently in drawdown.`,
          'info'
        );
      } else {
        toastStore.addToast('TP1 Completed', 'No eligible positions for TP1 scale-out.', 'info');
      }
    } catch (e: any) {
      toastStore.addToast('Error', e.message || 'Failed to execute TP1 scale-out', 'error');
    } finally {
      positionsStore.setIsActionInProgress(false);
    }
  };

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
      <Show when={count() > 0}>
        <div class="positions-bulk-toolbar">
          <div class="bulk-toolbar-summary">
            <span class="bulk-summary-badge">
              <span class="bulk-badge-dot" />
              <strong>{count()}</strong> Active Position{count() > 1 ? 's' : ''} ({totalVolume().toFixed(2)} Lots)
            </span>
            <span
              class="bulk-pnl-badge tabular-num"
              classList={{
                'text-profit': totalPnl() > 0,
                'text-loss': totalPnl() < 0,
                'text-neutral': totalPnl() === 0,
              }}
            >
              Floating P&L: {totalPnl() > 0 ? `+$${totalPnl().toFixed(2)}` : `$${totalPnl().toFixed(2)}`}
            </span>
          </div>

          <div class="bulk-toolbar-actions">
            <button
              type="button"
              class="btn-bulk-action btn-bulk-be"
              onClick={handleBreakEvenAllClick}
              disabled={positionsStore.isActionInProgress()}
              title="Universal Cost-Covering BE: Snaps SL to Entry + Spread/Fees for all profitable positions (skips trades in drawdown)"
            >
              <svg class="btn-bulk-svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10 1.944A11.954 11.954 0 012.166 5C2.056 5.649 2 6.319 2 7c0 5.225 3.34 9.67 8 11.317C14.66 16.67 18 12.225 18 7c0-.682-.057-1.35-.166-2.001A11.954 11.954 0 0110 1.944zM11 14a1 1 0 11-2 0 1 1 0 012 0zm0-7a1 1 0 10-2 0v3a1 1 0 102 0V7z" clip-rule="evenodd" />
              </svg>
              <span>🛡️ Set All to BE</span>
            </button>

            <button
              type="button"
              class="btn-bulk-action btn-bulk-half"
              onClick={handleClose50AllClick}
              disabled={positionsStore.isActionInProgress()}
              title="TP1 Workflow: Closes 50% volume and locks Break-Even on remaining volume for all profitable trades"
            >
              <svg class="btn-bulk-svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M5.5 2a3.5 3.5 0 101.996 6.368l2.584 2.584a3.5 3.5 0 101.414-1.414L8.91 6.954A3.5 3.5 0 005.5 2zm-1.5 3.5a1.5 1.5 0 113 0 1.5 1.5 0 01-3 0zm10 8a1.5 1.5 0 113 0 1.5 1.5 0 01-3 0z" clip-rule="evenodd" />
              </svg>
              <span>✂️ Close 50% & BE All</span>
            </button>

            <button
              type="button"
              class="btn-bulk-action btn-bulk-close-all"
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
              <svg class="btn-bulk-svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
              <span>
                {isArmedCloseAll()
                  ? `⚠️ Confirm Close ALL (${count()})`
                  : `🛑 Close All (${count()})`}
              </span>
            </button>
          </div>
        </div>
      </Show>

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
                <th class="text-right col-th-actions">Actions</th>
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

