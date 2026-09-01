import { Component, createSignal, createMemo, createEffect, onCleanup, Show } from 'solid-js';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';
import { positionsStore } from '../../stores/positionsStore';
import { marketStore } from '../../stores/marketStore';
import { formatCurrency } from '../../utils/formatters';
import { getAssetStepRule, stepPrice } from '../../utils/stepperEngine';

interface Props {
  ticket: number;
}

export const PositionRow: Component<Props> = (props) => {
  const position = createMemo(() => positionsStore.getPosition(props.ticket));

  let hubRef: HTMLDivElement | undefined;

  const [slValue, setSlValue] = createSignal<string>('');
  const [tpValue, setTpValue] = createSignal<string>('');
  const [isEditing, setIsEditing] = createSignal<boolean>(false);
  const [isSubmitting, setIsSubmitting] = createSignal<boolean>(false);

  const stepRule = createMemo(() => {
    const p = position();
    if (!p) return getAssetStepRule('EURUSD', 5);
    return getAssetStepRule(p.symbol, p.digits, p.pip_size, p.step_rule);
  });

  const startEditing = () => {
    const p = position();
    if (p) {
      setSlValue(p.sl ? p.sl.toFixed(p.digits) : '');
      setTpValue(p.tp ? p.tp.toFixed(p.digits) : '');
      setIsEditing(true);
    }
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  // Global Escape key and click-outside dismissal
  createEffect(() => {
    if (!isEditing()) return;

    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        cancelEditing();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (hubRef && !hubRef.contains(e.target as Node)) {
        cancelEditing();
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    const timer = setTimeout(() => {
      window.addEventListener('mousedown', handleClickOutside);
    }, 50);

    onCleanup(() => {
      window.removeEventListener('keydown', handleGlobalKeyDown);
      window.removeEventListener('mousedown', handleClickOutside);
      clearTimeout(timer);
    });
  });

  const stepSl = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const currentVal = slValue().trim() ? parseFloat(slValue()) : (p.sl || p.price_open);
    const newVal = stepPrice(currentVal, direction, rule, e);
    setSlValue(newVal > 0 ? newVal.toFixed(p.digits) : '');
  };

  const stepTp = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const currentVal = tpValue().trim() ? parseFloat(tpValue()) : (p.tp || p.price_open);
    const newVal = stepPrice(currentVal, direction, rule, e);
    setTpValue(newVal > 0 ? newVal.toFixed(p.digits) : '');
  };

  // Real-time live distance telemetry
  const slTelemetry = createMemo(() => {
    const p = position();
    if (!p) return null;
    const val = slValue().trim() ? parseFloat(slValue()) : p.sl;
    if (!val || val <= 0) return null;

    const rule = stepRule();
    const isBuy = p.type === 'BUY';
    const diff = isBuy ? p.price_open - val : val - p.price_open;
    const pips = diff / rule.pipSize;
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollarLoss = pips * p.volume * pipVal;

    return {
      pips: pips.toFixed(1),
      dollars: dollarLoss.toFixed(2),
      unit: rule.unitLabel,
    };
  });

  const tpTelemetry = createMemo(() => {
    const p = position();
    if (!p) return null;
    const val = tpValue().trim() ? parseFloat(tpValue()) : p.tp;
    if (!val || val <= 0) return null;

    const rule = stepRule();
    const isBuy = p.type === 'BUY';
    const diff = isBuy ? val - p.price_open : p.price_open - val;
    const pips = diff / rule.pipSize;
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollarGain = pips * p.volume * pipVal;

    return {
      pips: pips.toFixed(1),
      dollars: dollarGain.toFixed(2),
      unit: rule.unitLabel,
    };
  });

  // Quick Presets
  const applyBreakEvenSnap = () => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const spreadPips = calcResult?.spec?.spread_pips || 0.5;
    const bufferPips = spreadPips + 0.5; // Spread + 0.5p safety buffer
    const bufferDist = bufferPips * rule.pipSize;

    const bePrice = p.type === 'BUY'
      ? p.price_open + bufferDist
      : p.price_open - bufferDist;

    setSlValue(bePrice.toFixed(p.digits));
  };

  const applyAdrSnap = () => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const adrPips = calcResult?.spec?.adr_14_pips || 0;
    const slDistPips = adrPips > 0 ? adrPips / 4 : 15.0;
    const slDist = slDistPips * rule.pipSize;

    const adrPrice = p.type === 'BUY'
      ? p.price_open - slDist
      : p.price_open + slDist;

    setSlValue(adrPrice.toFixed(p.digits));
  };

  const applyRrSnap = (ratio: number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const currentSl = slValue().trim() ? parseFloat(slValue()) : p.sl;
    const slDist = currentSl > 0 ? Math.abs(p.price_open - currentSl) : 15 * rule.pipSize;
    const tpDist = slDist * ratio;

    const tpPrice = p.type === 'BUY'
      ? p.price_open + tpDist
      : p.price_open - tpDist;

    setTpValue(tpPrice.toFixed(p.digits));
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
      const rule = stepRule();
      const calcResult = marketStore.getCalculatedResult(p.symbol);
      const spreadPips = calcResult?.spec?.spread_pips || 0.5;
      const bufferDist = (spreadPips + 0.5) * rule.pipSize;

      const bePrice = p.type === 'BUY'
        ? p.price_open + bufferDist
        : p.price_open - bufferDist;

      const roundedBePrice = parseFloat(bePrice.toFixed(p.digits));
      const res = await api.modifyPosition(p.ticket, roundedBePrice, p.tp);
      if (res.success) {
        toastStore.addToast(
          'Break-Even Snapped',
          `SL snapped to ${roundedBePrice} (Entry + ${(spreadPips + 0.5).toFixed(1)} ${rule.unitLabel} spread buffer) for #${p.ticket}`,
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
        <tr
          class="position-row"
          classList={{
            'is-editing': isEditing(),
          }}
        >
          <td class="text-left">
            <div class="pos-ticket-cell">
              <span class="pos-ticket">#{pos().ticket}</span>
            </div>
          </td>

          <td class="text-left">
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

          <td class="text-right">
            <span class="pos-volume tabular-num">{pos().volume.toFixed(2)} Lots</span>
          </td>

          <td class="text-right">
            <span class="font-mono tabular-num">{pos().price_open.toFixed(pos().digits)}</span>
          </td>

          <td class="text-right">
            <span class="font-mono tabular-num">{pos().price_current.toFixed(pos().digits)}</span>
          </td>

          <td class="text-right">
            <div class="pos-pnl-cell text-right">
              <span
                class="pos-profit tabular-num"
                classList={{
                  'text-profit': pos().profit > 0,
                  'text-loss': pos().profit < 0,
                  'text-neutral': pos().profit === 0,
                }}
              >
                {pos().profit > 0
                  ? `+${formatCurrency(pos().profit)}`
                  : pos().profit < 0
                  ? formatCurrency(pos().profit)
                  : `$0.00`}
              </span>
              <span class="pos-pips-sub tabular-num">
                ({pos().pnl_pips > 0 ? `+${pos().pnl_pips}` : pos().pnl_pips} {stepRule().unitLabel})
              </span>
            </div>
          </td>

          <td class="text-center">
            <Show
              when={pos().r_multiple !== null}
              fallback={<span class="text-muted">—</span>}
            >
              <span
                class="r-multiple-pill tabular-num"
                classList={{
                  'r-profit': (pos().r_multiple || 0) > 0,
                  'r-loss': (pos().r_multiple || 0) < 0,
                  'r-neutral': (pos().r_multiple || 0) === 0,
                }}
              >
                {(pos().r_multiple || 0) > 0
                  ? `+${pos().r_multiple} R`
                  : `${pos().r_multiple || 0} R`}
              </span>
            </Show>
          </td>

          <td class="pos-sltp-td text-center">
            <div class="pos-sltp-cell">
              <Show
                when={isEditing()}
                fallback={
                  <div
                    class="sltp-display"
                    onClick={startEditing}
                    title="Click to edit SL / TP with live steppers & presets"
                  >
                    <div class="sltp-display-badges">
                      <span class="sltp-val sl-pill tabular-num">
                        SL: {pos().sl ? pos().sl.toFixed(pos().digits) : 'None'}
                      </span>
                      <span class="sltp-val tp-pill tabular-num">
                        TP: {pos().tp ? pos().tp.toFixed(pos().digits) : 'None'}
                      </span>
                    </div>
                    <span class="edit-icon">
                      <svg class="edit-icon-svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                    </span>
                  </div>
                }
              >
                <div class="sltp-edit-hub" ref={hubRef}>
                  <div class="sltp-steppers-row">
                    {/* SL Stepper */}
                    <div class="sltp-field-group">
                      <label class="sltp-field-label sl-label">SL</label>
                      <div class="sltp-stepper-box">
                        <button
                          type="button"
                          class="btn-stepper-mini"
                          onClick={(e) => stepSl('DOWN', e)}
                          title={`-1 ${stepRule().unitLabel} (Shift: -10, Alt: -0.1)`}
                        >
                          −
                        </button>
                        <input
                          type="number"
                          class="sltp-mini-input tabular-num"
                          placeholder="SL Price"
                          min="0"
                          step={stepRule().normalStep}
                          value={slValue()}
                          onFocus={(e) => e.currentTarget.select()}
                          onInput={(e) => setSlValue(e.currentTarget.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'ArrowUp') {
                              e.preventDefault();
                              stepSl('UP', e);
                            } else if (e.key === 'ArrowDown') {
                              e.preventDefault();
                              stepSl('DOWN', e);
                            } else if (e.key === 'Enter') {
                              handleSaveSltp();
                            } else if (e.key === 'Escape') {
                              cancelEditing();
                            }
                          }}
                        />
                        <button
                          type="button"
                          class="btn-stepper-mini"
                          onClick={(e) => stepSl('UP', e)}
                          title={`+1 ${stepRule().unitLabel} (Shift: +10, Alt: +0.1)`}
                        >
                          +
                        </button>
                      </div>
                      <Show when={slTelemetry()}>
                        {(tel) => (
                          <span class="sltp-telemetry-badge sl-telemetry tabular-num">
                            -{tel().pips} {tel().unit} (-${tel().dollars})
                          </span>
                        )}
                      </Show>
                    </div>

                    {/* TP Stepper */}
                    <div class="sltp-field-group">
                      <label class="sltp-field-label tp-label">TP</label>
                      <div class="sltp-stepper-box">
                        <button
                          type="button"
                          class="btn-stepper-mini"
                          onClick={(e) => stepTp('DOWN', e)}
                          title={`-1 ${stepRule().unitLabel} (Shift: -10, Alt: -0.1)`}
                        >
                          −
                        </button>
                        <input
                          type="number"
                          class="sltp-mini-input tabular-num"
                          placeholder="TP Price"
                          min="0"
                          step={stepRule().normalStep}
                          value={tpValue()}
                          onFocus={(e) => e.currentTarget.select()}
                          onInput={(e) => setTpValue(e.currentTarget.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'ArrowUp') {
                              e.preventDefault();
                              stepTp('UP', e);
                            } else if (e.key === 'ArrowDown') {
                              e.preventDefault();
                              stepTp('DOWN', e);
                            } else if (e.key === 'Enter') {
                              handleSaveSltp();
                            } else if (e.key === 'Escape') {
                              cancelEditing();
                            }
                          }}
                        />
                        <button
                          type="button"
                          class="btn-stepper-mini"
                          onClick={(e) => stepTp('UP', e)}
                          title={`+1 ${stepRule().unitLabel} (Shift: +10, Alt: +0.1)`}
                        >
                          +
                        </button>
                      </div>
                      <Show when={tpTelemetry()}>
                        {(tel) => (
                          <span class="sltp-telemetry-badge tp-telemetry tabular-num">
                            +{tel().pips} {tel().unit} (+${tel().dollars})
                          </span>
                        )}
                      </Show>
                    </div>

                    {/* Action buttons */}
                    <div class="sltp-hub-actions">
                      <button
                        type="button"
                        class="btn-sltp-save"
                        onClick={handleSaveSltp}
                        disabled={isSubmitting()}
                        title="Commit SL/TP modifications to MT5 (Enter)"
                      >
                        ✓
                      </button>
                      <button
                        type="button"
                        class="btn-sltp-cancel"
                        onClick={cancelEditing}
                        title="Cancel (Escape)"
                      >
                        ✕
                      </button>
                    </div>
                  </div>

                  {/* 1-Click Quick Presets */}
                  <div class="sltp-quick-presets">
                    <button
                      type="button"
                      class="btn-preset-pill"
                      onClick={applyBreakEvenSnap}
                      title="Snap SL to Entry + Spread Buffer"
                    >
                      🛡️ BE Snap
                    </button>
                    <button
                      type="button"
                      class="btn-preset-pill"
                      onClick={applyAdrSnap}
                      title="Snap SL to 1/4 ADR distance"
                    >
                      📐 1/4 ADR
                    </button>
                    <button
                      type="button"
                      class="btn-preset-pill"
                      onClick={() => applyRrSnap(1.5)}
                      title="Set TP to 1:1.5 Risk-Reward Ratio"
                    >
                      🎯 1:1.5 RR
                    </button>
                    <button
                      type="button"
                      class="btn-preset-pill"
                      onClick={() => applyRrSnap(2.0)}
                      title="Set TP to 1:2.0 Risk-Reward Ratio"
                    >
                      🎯 1:2 RR
                    </button>
                  </div>
                </div>
              </Show>
            </div>
          </td>

          <td class="text-right">
            <div class="pos-actions-segmented">
              <div class="pos-actions-defensive">
                <button
                  class="btn-pos-action btn-pos-be"
                  onClick={handleMoveToBreakEven}
                  disabled={isSubmitting()}
                  title="Move Stop Loss to Entry Price + Spread Offset (True Zero-Loss Scratch)"
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
              </div>

              <div class="pos-action-divider" />

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
