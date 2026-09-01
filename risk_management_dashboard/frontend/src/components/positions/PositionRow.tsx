import { Component, createSignal, Show } from 'solid-js';
import { OpenPosition } from '../../types';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';
import { positionsStore } from '../../stores/positionsStore';
import { formatCurrency } from '../../utils/formatters';

interface Props {
  position: OpenPosition;
}

export const PositionRow: Component<Props> = (props) => {
  const [slValue, setSlValue] = createSignal<number>(props.position.sl || 0.0);
  const [tpValue, setTpValue] = createSignal<number>(props.position.tp || 0.0);
  const [isEditing, setIsEditing] = createSignal<boolean>(false);
  const [isSubmitting, setIsSubmitting] = createSignal<boolean>(false);

  const handleClosePosition = async (volume?: number) => {
    try {
      setIsSubmitting(true);
      const res = await api.closePosition(props.position.ticket, volume);
      if (res.success) {
        toastStore.addToast(
          'Position Closed',
          res.message || `Closed #${props.position.ticket} ${props.position.symbol}`,
          'success'
        );
      } else {
        toastStore.addToast('Close Failed', res.message, 'error');
      }
    } catch (e: any) {
      toastStore.addToast('Error', e.message || 'Failed to close position', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMoveToBreakEven = async () => {
    try {
      setIsSubmitting(true);
      // Snapping SL to entry price
      const entryPrice = props.position.price_open;
      const res = await api.modifyPosition(props.position.ticket, entryPrice, props.position.tp);
      if (res.success) {
        setSlValue(entryPrice);
        toastStore.addToast(
          'Break-Even Snapped',
          `SL moved to entry price (${entryPrice}) for #${props.position.ticket}`,
          'success'
        );
      } else {
        toastStore.addToast('Modification Failed', res.message, 'error');
      }
    } catch (e: any) {
      toastStore.addToast('Error', e.message || 'Failed to snap to break-even', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveSltp = async () => {
    try {
      setIsSubmitting(true);
      const res = await api.modifyPosition(props.position.ticket, slValue(), tpValue());
      if (res.success) {
        setIsEditing(false);
        toastStore.addToast('SL/TP Updated', res.message, 'success');
      } else {
        toastStore.addToast('Modification Failed', res.message, 'error');
      }
    } catch (e: any) {
      toastStore.addToast('Error', e.message || 'Failed to modify SL/TP', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <tr class="position-row">
      <td>
        <div class="pos-ticket-cell">
          <span class="pos-ticket">#{props.position.ticket}</span>
        </div>
      </td>

      <td>
        <div class="pos-symbol-cell">
          <strong class="pos-symbol">{props.position.symbol}</strong>
          <span
            class="pos-type-badge"
            classList={{
              'badge-buy': props.position.type === 'BUY',
              'badge-sell': props.position.type === 'SELL',
            }}
          >
            {props.position.type}
          </span>
        </div>
      </td>

      <td>
        <span class="pos-volume">{props.position.volume.toFixed(2)} Lots</span>
      </td>

      <td>
        <span class="font-mono">{props.position.price_open.toFixed(props.position.digits)}</span>
      </td>

      <td>
        <span class="font-mono">{props.position.price_current.toFixed(props.position.digits)}</span>
      </td>

      <td>
        <div class="pos-pnl-cell">
          <span
            class="pos-profit"
            classList={{
              'text-profit': props.position.profit > 0,
              'text-loss': props.position.profit < 0,
            }}
          >
            {props.position.profit >= 0
              ? `+${formatCurrency(props.position.profit)}`
              : formatCurrency(props.position.profit)}
          </span>
          <span class="pos-pips-sub">
            ({props.position.pnl_pips >= 0 ? `+${props.position.pnl_pips}` : props.position.pnl_pips} pips)
          </span>
        </div>
      </td>

      <td>
        <Show
          when={props.position.r_multiple !== null}
          fallback={<span class="text-muted">—</span>}
        >
          <span
            class="r-multiple-pill"
            classList={{
              'r-profit': (props.position.r_multiple || 0) > 0,
              'r-loss': (props.position.r_multiple || 0) < 0,
            }}
          >
            {props.position.r_multiple! >= 0
              ? `+${props.position.r_multiple} R`
              : `${props.position.r_multiple} R`}
          </span>
        </Show>
      </td>

      <td>
        <div class="pos-sltp-cell">
          <Show
            when={isEditing()}
            fallback={
              <div class="sltp-display" onClick={() => setIsEditing(true)} title="Click to edit SL / TP">
                <span class="sltp-val">SL: {props.position.sl || 'None'}</span>
                <span class="sltp-val">TP: {props.position.tp || 'None'}</span>
                <span class="edit-icon">✏️</span>
              </div>
            }
          >
            <div class="sltp-edit-form">
              <input
                type="number"
                class="sltp-mini-input"
                placeholder="SL Price"
                step="0.0001"
                value={slValue()}
                onInput={(e) => setSlValue(parseFloat(e.currentTarget.value) || 0)}
              />
              <input
                type="number"
                class="sltp-mini-input"
                placeholder="TP Price"
                step="0.0001"
                value={tpValue()}
                onInput={(e) => setTpValue(parseFloat(e.currentTarget.value) || 0)}
              />
              <button
                class="btn-xs btn-primary"
                onClick={handleSaveSltp}
                disabled={isSubmitting()}
              >
                Save
              </button>
              <button
                class="btn-xs btn-ghost"
                onClick={() => setIsEditing(false)}
              >
                ✕
              </button>
            </div>
          </Show>
        </div>
      </td>

      <td class="text-center">
        <div class="pos-actions-group">
          <button
            class="btn-pos-action btn-pos-be"
            onClick={handleMoveToBreakEven}
            disabled={isSubmitting()}
            title="Move Stop Loss to Entry Price (Break-Even)"
          >
            🛡️ BE
          </button>

          <button
            class="btn-pos-action btn-pos-half"
            onClick={() => handleClosePosition(props.position.volume / 2)}
            disabled={isSubmitting()}
            title="Close 50% of position volume"
          >
            ✂️ 50%
          </button>

          <button
            class="btn-pos-action btn-pos-close"
            onClick={() => handleClosePosition()}
            disabled={isSubmitting()}
            title="Instantly liquidate position at market price"
          >
            ✕ Close
          </button>
        </div>
      </td>
    </tr>
  );
};
