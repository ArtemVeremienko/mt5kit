import { Component, createSignal, createMemo, Show } from 'solid-js';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';
import { positionsStore } from '../../stores/positionsStore';
import { formatCurrency } from '../../utils/formatters';

interface Props {
  ticket: number;
}

export const PositionRow: Component<Props> = (props) => {
  const position = createMemo(() => positionsStore.getPosition(props.ticket));

  const [slValue, setSlValue] = createSignal<string>('');
  const [tpValue, setTpValue] = createSignal<string>('');
  const [isEditing, setIsEditing] = createSignal<boolean>(false);
  const [isSubmitting, setIsSubmitting] = createSignal<boolean>(false);

  const startEditing = () => {
    const p = position();
    if (p) {
      setSlValue(p.sl ? p.sl.toString() : '');
      setTpValue(p.tp ? p.tp.toString() : '');
      setIsEditing(true);
    }
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  const handleClosePosition = async (volume?: number) => {
    const p = position();
    if (!p) return;
    try {
      setIsSubmitting(true);
      const res = await api.closePosition(p.ticket, volume);
      if (res.success) {
        toastStore.addToast(
          'Position Closed',
          res.message || `Closed #${p.ticket} ${p.symbol}`,
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
    const p = position();
    if (!p) return;
    try {
      setIsSubmitting(true);
      // Snapping SL to entry price
      const entryPrice = p.price_open;
      const res = await api.modifyPosition(p.ticket, entryPrice, p.tp);
      if (res.success) {
        toastStore.addToast(
          'Break-Even Snapped',
          `SL moved to entry price (${entryPrice}) for #${p.ticket}`,
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
    const p = position();
    if (!p) return;
    try {
      setIsSubmitting(true);
      const slNum = slValue().trim() ? parseFloat(slValue()) : 0;
      const tpNum = tpValue().trim() ? parseFloat(tpValue()) : 0;
      const res = await api.modifyPosition(p.ticket, slNum, tpNum);
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
    <Show when={position()}>
      {(pos) => (
        <tr class="position-row">
          <td>
            <div class="pos-ticket-cell">
              <span class="pos-ticket">#{pos().ticket}</span>
            </div>
          </td>

          <td>
            <div class="pos-symbol-cell">
              <strong class="pos-symbol">{pos().symbol}</strong>
              <span
                class="pos-type-badge"
                classList={{
                  'badge-buy': pos().type === 'BUY',
                  'badge-sell': pos().type === 'SELL',
                }}
              >
                {pos().type}
              </span>
            </div>
          </td>

          <td>
            <span class="pos-volume">{pos().volume.toFixed(2)} Lots</span>
          </td>

          <td>
            <span class="font-mono">{pos().price_open.toFixed(pos().digits)}</span>
          </td>

          <td>
            <span class="font-mono">{pos().price_current.toFixed(pos().digits)}</span>
          </td>

          <td>
            <div class="pos-pnl-cell">
              <span
                class="pos-profit"
                classList={{
                  'text-profit': pos().profit > 0,
                  'text-loss': pos().profit < 0,
                }}
              >
                {pos().profit >= 0
                  ? `+${formatCurrency(pos().profit)}`
                  : formatCurrency(pos().profit)}
              </span>
              <span class="pos-pips-sub">
                ({pos().pnl_pips >= 0 ? `+${pos().pnl_pips}` : pos().pnl_pips} pips)
              </span>
            </div>
          </td>

          <td>
            <Show
              when={pos().r_multiple !== null}
              fallback={<span class="text-muted">—</span>}
            >
              <span
                class="r-multiple-pill"
                classList={{
                  'r-profit': (pos().r_multiple || 0) > 0,
                  'r-loss': (pos().r_multiple || 0) < 0,
                }}
              >
                {pos().r_multiple! >= 0
                  ? `+${pos().r_multiple} R`
                  : `${pos().r_multiple} R`}
              </span>
            </Show>
          </td>

          <td>
            <div class="pos-sltp-cell">
              <Show
                when={isEditing()}
                fallback={
                  <div
                    class="sltp-display"
                    onClick={startEditing}
                    title="Click to edit SL / TP"
                  >
                    <span class="sltp-val">SL: {pos().sl ? pos().sl.toFixed(pos().digits) : 'None'}</span>
                    <span class="sltp-val">TP: {pos().tp ? pos().tp.toFixed(pos().digits) : 'None'}</span>
                    <span class="edit-icon">✏️</span>
                  </div>
                }
              >
                <div class="sltp-edit-form">
                  <input
                    type="number"
                    class="sltp-mini-input tabular-num"
                    placeholder="SL Price"
                    step="any"
                    value={slValue()}
                    onFocus={(e) => e.currentTarget.select()}
                    onInput={(e) => setSlValue(e.currentTarget.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSaveSltp();
                      if (e.key === 'Escape') cancelEditing();
                    }}
                  />
                  <input
                    type="number"
                    class="sltp-mini-input tabular-num"
                    placeholder="TP Price"
                    step="any"
                    value={tpValue()}
                    onFocus={(e) => e.currentTarget.select()}
                    onInput={(e) => setTpValue(e.currentTarget.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSaveSltp();
                      if (e.key === 'Escape') cancelEditing();
                    }}
                  />
                  <button
                    class="btn-xs btn-primary"
                    onClick={handleSaveSltp}
                    disabled={isSubmitting()}
                    title="Save SL/TP modifications"
                  >
                    Save
                  </button>
                  <button
                    class="btn-xs btn-ghost"
                    onClick={cancelEditing}
                    title="Cancel editing"
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
                onClick={() => handleClosePosition(pos().volume / 2)}
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
      )}
    </Show>
  );
};
