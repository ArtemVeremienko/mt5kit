import { Component, Show, createSignal } from 'solid-js';
import { CalculatedSymbolResult } from '../../types';
import { preferencesStore } from '../../stores/preferencesStore';
import { toastStore } from '../../stores/toastStore';
import { formatRrRatio } from '../../utils/formatters';

interface Props {
  trade: {
    item: CalculatedSymbolResult;
    action: 'BUY' | 'SELL';
  } | null;
  onConfirm: () => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export const ConfirmTradeModal: Component<Props> = (props) => {
  const [rememberOneClick, setRememberOneClick] = createSignal<boolean>(false);

  const handleExecute = () => {
    if (rememberOneClick()) {
      preferencesStore.setOneClickEnabled(true);
      toastStore.addToast(
        '⚡ 1-Click Trading Enabled',
        'Future orders will execute immediately. You can re-enable confirmation in Settings.',
        'warning'
      );
    }
    props.onConfirm();
  };

  return (
    <Show when={props.trade}>
      {(trade) => (
        <div class="modal-backdrop" onClick={props.onCancel}>
          <div class="modal-card" onClick={(e) => e.stopPropagation()}>
            <div class="modal-header">
              <div class="modal-title-group">
                <span class="modal-icon">🛡️</span>
                <h3 class="modal-title">Confirm Order Execution</h3>
              </div>
              <button class="modal-close-btn" onClick={props.onCancel}>
                ✕
              </button>
            </div>

            <div class="modal-body">
              <div class="confirm-summary-box">
                <div class="confirm-action-row">
                  <span
                    class="badge-order-action"
                    classList={{
                      'badge-buy': trade().action === 'BUY',
                      'badge-sell': trade().action === 'SELL',
                    }}
                  >
                    {trade().action}
                  </span>
                  <strong class="confirm-symbol">{trade().item.spec.symbol}</strong>
                  <span class="confirm-lot">{trade().item.calc.lot_display} Lots</span>
                </div>

                <div class="confirm-details-list">
                  <div class="confirm-detail-row">
                    <span>Execution Price:</span>
                    <strong>
                      {trade().action === 'BUY'
                        ? trade().item.spec.ask_display
                        : trade().item.spec.bid_display}
                    </strong>
                  </div>
                  <div class="confirm-detail-row">
                    <span>Stop Loss:</span>
                    <span>{trade().item.calc.sl_pips} Pips</span>
                  </div>
                  <div class="confirm-detail-row">
                    <span>Take Profit:</span>
                    <span>
                      {preferencesStore.rrRatio() > 0
                        ? `${(trade().item.calc.sl_pips * preferencesStore.rrRatio()).toFixed(1)} Pips (${formatRrRatio(preferencesStore.rrRatio(), { showUnit: false })})`
                        : 'None (Manual Exit)'}
                    </span>
                  </div>
                  <div class="confirm-detail-row">
                    <span>Effective Risk:</span>
                    <strong class="text-accent">{trade().item.calc.risk_display}</strong>
                  </div>
                  <div class="confirm-detail-row">
                    <span>Required Margin:</span>
                    <span>${trade().item.calc.required_margin_display}</span>
                  </div>
                </div>
              </div>

              <div class="confirm-optin-box">
                <label class="confirm-checkbox-label">
                  <input
                    type="checkbox"
                    class="confirm-checkbox"
                    checked={rememberOneClick()}
                    onChange={(e) => setRememberOneClick(e.currentTarget.checked)}
                  />
                  <span class="confirm-checkbox-text">
                    Don't show this confirmation again (Enable 1-Click Trading)
                  </span>
                </label>
              </div>
            </div>

            <div class="modal-footer">
              <button class="btn-ghost" onClick={props.onCancel} disabled={props.isSubmitting}>
                Cancel
              </button>
              <button
                class="btn-primary"
                classList={{
                  'btn-buy': trade().action === 'BUY',
                  'btn-sell': trade().action === 'SELL',
                }}
                onClick={handleExecute}
                disabled={props.isSubmitting}
              >
                {props.isSubmitting ? 'Executing...' : `Execute ${trade().action}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </Show>
  );
};
