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
  let slInputRef: HTMLInputElement | undefined;
  let tpInputRef: HTMLInputElement | undefined;

  const [slValue, setSlValue] = createSignal<string>('');
  const [tpValue, setTpValue] = createSignal<string>('');
  const [isEditing, setIsEditing] = createSignal<boolean>(false);
  const [isSubmitting, setIsSubmitting] = createSignal<boolean>(false);

  const stepRule = createMemo(() => {
    const p = position();
    if (!p) return getAssetStepRule('EURUSD', 5);
    return getAssetStepRule(p.symbol, p.digits, p.pip_size, p.step_rule);
  });

  const startEditing = (field: 'SL' | 'TP' = 'SL') => {
    const p = position();
    if (p) {
      setSlValue(p.sl ? p.sl.toFixed(p.digits) : '');
      setTpValue(p.tp ? p.tp.toFixed(p.digits) : '');
      setIsEditing(true);

      // Auto-focus requested field with selection
      setTimeout(() => {
        if (field === 'SL' && slInputRef) {
          slInputRef.focus();
          slInputRef.select();
        } else if (field === 'TP' && tpInputRef) {
          tpInputRef.focus();
          tpInputRef.select();
        }
      }, 50);
    }
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  // Global Escape key, Enter key, and click-outside dismissal
  createEffect(() => {
    if (!isEditing()) return;

    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        cancelEditing();
      } else if (e.key === 'Enter') {
        // If Enter is pressed while inside popover, commit changes instead of triggering focused buttons
        e.preventDefault();
        e.stopPropagation();
        handleSaveSltp();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (hubRef && !hubRef.contains(e.target as Node)) {
        cancelEditing();
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown, true);
    const timer = setTimeout(() => {
      window.addEventListener('mousedown', handleClickOutside);
    }, 50);

    onCleanup(() => {
      window.removeEventListener('keydown', handleGlobalKeyDown, true);
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

  // Real-time live distance telemetry with explicit sign calculation
  const slTelemetry = createMemo(() => {
    const p = position();
    if (!p) return null;
    const val = slValue().trim() ? parseFloat(slValue()) : p.sl;
    if (!val || val <= 0) return null;

    const rule = stepRule();
    const isBuy = p.type === 'BUY';
    const diff = isBuy ? p.price_open - val : val - p.price_open;
    const pips = diff / rule.pipSize;
    const isRisk = pips >= 0;
    const absPips = Math.abs(pips);
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollarAmount = absPips * p.volume * pipVal;

    return {
      absPips: absPips.toFixed(1),
      isRisk,
      dollarText: dollarAmount.toFixed(2),
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
    const isGain = diff >= 0;
    const absPips = Math.abs(pips);
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollarAmount = absPips * p.volume * pipVal;

    return {
      absPips: absPips.toFixed(1),
      isGain,
      dollarText: dollarAmount.toFixed(2),
      unit: rule.unitLabel,
    };
  });

  // Display telemetry for row cells (when not editing)
  const currentSlRowInfo = createMemo(() => {
    const p = position();
    if (!p || !p.sl || p.sl <= 0) return null;
    const rule = stepRule();
    const isBuy = p.type === 'BUY';
    const diff = isBuy ? p.price_open - p.sl : p.sl - p.price_open;
    const pips = diff / rule.pipSize;
    const isRisk = pips >= 0;
    const absPips = Math.abs(pips);
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollarAmount = absPips * p.volume * pipVal;

    return {
      price: p.sl.toFixed(p.digits),
      pipText: `${isRisk ? '-' : '+'}${absPips.toFixed(1)} ${rule.unitLabel}`,
      dollarText: `${isRisk ? '-$' : '+$'}${dollarAmount.toFixed(2)}`,
      isRisk,
    };
  });

  const currentTpRowInfo = createMemo(() => {
    const p = position();
    if (!p || !p.tp || p.tp <= 0) return null;
    const rule = stepRule();
    const isBuy = p.type === 'BUY';
    const diff = isBuy ? p.tp - p.price_open : p.price_open - p.tp;
    const pips = diff / rule.pipSize;
    const isGain = diff >= 0;
    const absPips = Math.abs(pips);
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollarAmount = absPips * p.volume * pipVal;

    return {
      price: p.tp.toFixed(p.digits),
      pipText: `${isGain ? '+' : '-'}${absPips.toFixed(1)} ${rule.unitLabel}`,
      dollarText: `${isGain ? '+$' : '-$'}${dollarAmount.toFixed(2)}`,
      isGain,
    };
  });

  // Quick Presets
  const applyBreakEvenSnap = () => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const spreadPips = calcResult?.spec?.spread_pips || 0.5;
    const bufferPips = spreadPips + 0.5;
    const bufferDist = bufferPips * rule.pipSize;

    const bePrice = p.type === 'BUY'
      ? p.price_open + bufferDist
      : p.price_open - bufferDist;

    setSlValue(bePrice.toFixed(p.digits));
  };

  const applyAdrSlSnap = (fraction: number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const adrPips = calcResult?.spec?.adr_14_pips || 0;
    const slDistPips = adrPips > 0 ? adrPips * fraction : 15.0;
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
    if (!p || isSubmitting()) return;
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
          {/* 1. Ticket */}
          <td class="text-left pos-cell-ticket">
            <span class="pos-ticket">#{pos().ticket}</span>
          </td>

          {/* 2. Symbol & Side */}
          <td class="text-left pos-cell-symbol">
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

          {/* 3. Volume */}
          <td class="text-right pos-cell-volume">
            <span class="pos-volume tabular-num">{pos().volume.toFixed(2)} Lots</span>
          </td>

          {/* 4. Open Price */}
          <td class="text-right pos-cell-open">
            <span class="font-mono tabular-num">{pos().price_open.toFixed(pos().digits)}</span>
          </td>

          {/* 5. Current Price */}
          <td class="text-right pos-cell-current">
            <span class="font-mono tabular-num">{pos().price_current.toFixed(pos().digits)}</span>
          </td>

          {/* 6. Stop Loss (Dedicated Column) */}
          <td class="text-center pos-cell-sl" onClick={() => startEditing('SL')}>
            <div class="sltp-col-cell sl-col-cell">
              <Show
                when={currentSlRowInfo()}
                fallback={
                  <button type="button" class="btn-set-target-empty sl-empty-btn">
                    + Set SL
                  </button>
                }
              >
                {(info) => (
                  <div class="sltp-display-stacked">
                    <span class="sltp-price-val sl-price-val tabular-num">{info().price}</span>
                    <span
                      class="sltp-sub-telemetry tabular-num"
                      classList={{
                        'text-risk': info().isRisk,
                        'text-profit': !info().isRisk,
                      }}
                    >
                      {info().pipText} ({info().dollarText})
                    </span>
                  </div>
                )}
              </Show>
              <span class="sltp-edit-affordance" title="Click to adjust Stop Loss & Take Profit">
                ✎
              </span>
            </div>
          </td>

          {/* 7. Take Profit (Dedicated Column) */}
          <td class="text-center pos-cell-tp" onClick={() => startEditing('TP')}>
            <div class="sltp-col-cell tp-col-cell">
              <Show
                when={currentTpRowInfo()}
                fallback={
                  <button type="button" class="btn-set-target-empty tp-empty-btn">
                    + Set TP
                  </button>
                }
              >
                {(info) => (
                  <div class="sltp-display-stacked">
                    <span class="sltp-price-val tp-price-val tabular-num">{info().price}</span>
                    <span
                      class="sltp-sub-telemetry tabular-num"
                      classList={{
                        'text-profit': info().isGain,
                        'text-loss': !info().isGain,
                      }}
                    >
                      {info().pipText} ({info().dollarText})
                    </span>
                  </div>
                )}
              </Show>
              <span class="sltp-edit-affordance" title="Click to adjust Stop Loss & Take Profit">
                ✎
              </span>
            </div>

            {/* Contextual SL/TP Edit Popover Anchored to the Risk Columns */}
            <Show when={isEditing()}>
              <div class="sltp-edit-hub" ref={hubRef} onClick={(e) => e.stopPropagation()}>
                <div class="sltp-hub-header">
                  <span class="sltp-hub-title">
                    Modify SL/TP · <strong>{pos().symbol}</strong> (#{pos().ticket})
                  </span>
                  <button
                    type="button"
                    class="btn-sltp-close-icon"
                    onClick={cancelEditing}
                    title="Close (Esc)"
                    tabindex="-1"
                  >
                    ✕
                  </button>
                </div>

                <div class="sltp-hub-body">
                  {/* Left Column: Stop Loss Field & Presets */}
                  <div class="sltp-hub-column sl-column">
                    <div class="sltp-column-header">
                      <label class="sltp-field-label sl-label">Stop Loss</label>
                      <Show when={slTelemetry()}>
                        {(tel) => (
                          <span
                            class="sltp-telemetry-badge sl-telemetry tabular-num"
                            classList={{
                              'text-risk': tel().isRisk,
                              'text-profit': !tel().isRisk,
                            }}
                          >
                            {tel().isRisk ? '-' : '+'}{tel().absPips} {tel().unit} ({tel().isRisk ? `-$${tel().dollarText}` : `+$${tel().dollarText}`})
                          </span>
                        )}
                      </Show>
                    </div>

                    <div class="sltp-stepper-box">
                      <button
                        type="button"
                        class="btn-stepper-touch"
                        onClick={(e) => stepSl('DOWN', e)}
                        title={`-1 ${stepRule().unitLabel} (Shift: -10, Alt: -0.1)`}
                        tabindex="-1"
                      >
                        −
                      </button>
                      <input
                        ref={slInputRef}
                        type="number"
                        class="sltp-input-main tabular-num"
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
                          }
                        }}
                      />
                      <button
                        type="button"
                        class="btn-stepper-touch"
                        onClick={(e) => stepSl('UP', e)}
                        title={`+1 ${stepRule().unitLabel} (Shift: +10, Alt: +0.1)`}
                        tabindex="-1"
                      >
                        +
                      </button>
                    </div>

                    <div class="sltp-presets-group">
                      <span class="preset-group-title">SL Presets</span>
                      <div class="preset-chips-row">
                        <button
                          type="button"
                          class="btn-preset-chip"
                          onClick={applyBreakEvenSnap}
                          title="Snap SL to Entry Price + Spread Buffer"
                          tabindex="-1"
                        >
                          🛡️ Entry / BE
                        </button>
                        <button
                          type="button"
                          class="btn-preset-chip"
                          onClick={() => applyAdrSlSnap(0.25)}
                          title="Snap SL to 1/4 ADR distance"
                          tabindex="-1"
                        >
                          📐 1/4 ADR
                        </button>
                        <button
                          type="button"
                          class="btn-preset-chip"
                          onClick={() => applyAdrSlSnap(0.5)}
                          title="Snap SL to 1/2 ADR distance"
                          tabindex="-1"
                        >
                          📐 1/2 ADR
                        </button>
                      </div>
                    </div>
                  </div>

                  <div class="sltp-hub-divider" />

                  {/* Right Column: Take Profit Field & Presets */}
                  <div class="sltp-hub-column tp-column">
                    <div class="sltp-column-header">
                      <label class="sltp-field-label tp-label">Take Profit</label>
                      <Show when={tpTelemetry()}>
                        {(tel) => (
                          <span
                            class="sltp-telemetry-badge tp-telemetry tabular-num"
                            classList={{
                              'text-profit': tel().isGain,
                              'text-risk': !tel().isGain,
                            }}
                          >
                            {tel().isGain ? '+' : '-'}{tel().absPips} {tel().unit} ({tel().isGain ? `+$${tel().dollarText}` : `-$${tel().dollarText}`})
                          </span>
                        )}
                      </Show>
                    </div>

                    <div class="sltp-stepper-box">
                      <button
                        type="button"
                        class="btn-stepper-touch"
                        onClick={(e) => stepTp('DOWN', e)}
                        title={`-1 ${stepRule().unitLabel} (Shift: -10, Alt: -0.1)`}
                        tabindex="-1"
                      >
                        −
                      </button>
                      <input
                        ref={tpInputRef}
                        type="number"
                        class="sltp-input-main tabular-num"
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
                          }
                        }}
                      />
                      <button
                        type="button"
                        class="btn-stepper-touch"
                        onClick={(e) => stepTp('UP', e)}
                        title={`+1 ${stepRule().unitLabel} (Shift: +10, Alt: +0.1)`}
                        tabindex="-1"
                      >
                        +
                      </button>
                    </div>

                    <div class="sltp-presets-group">
                      <span class="preset-group-title">TP Presets</span>
                      <div class="preset-chips-row">
                        <button
                          type="button"
                          class="btn-preset-chip"
                          onClick={() => applyRrSnap(1.5)}
                          title="Set TP to 1:1.5 Risk-Reward Ratio"
                          tabindex="-1"
                        >
                          🎯 1:1.5 RR
                        </button>
                        <button
                          type="button"
                          class="btn-preset-chip"
                          onClick={() => applyRrSnap(2.0)}
                          title="Set TP to 1:2 Risk-Reward Ratio"
                          tabindex="-1"
                        >
                          🎯 1:2 RR
                        </button>
                        <button
                          type="button"
                          class="btn-preset-chip"
                          onClick={() => applyRrSnap(3.0)}
                          title="Set TP to 1:3 Risk-Reward Ratio"
                          tabindex="-1"
                        >
                          🎯 1:3 RR
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer Controls: Apply & Cancel */}
                <div class="sltp-hub-footer">
                  <button
                    type="button"
                    class="btn-sltp-cancel-text"
                    onClick={cancelEditing}
                    disabled={isSubmitting()}
                    tabindex="-1"
                  >
                    Cancel (Esc)
                  </button>
                  <button
                    type="button"
                    class="btn-sltp-apply-main"
                    onClick={handleSaveSltp}
                    disabled={isSubmitting()}
                  >
                    {isSubmitting() ? 'Submitting...' : '💾 Apply Changes (Enter)'}
                  </button>
                </div>
              </div>
            </Show>
          </td>

          {/* 8. Floating P&L */}
          <td class="text-right pos-cell-pnl">
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
                  : formatCurrency(pos().profit)}
              </span>
              <span class="pos-pips-sub tabular-num">
                ({pos().pnl_pips > 0 ? `+${pos().pnl_pips}` : pos().pnl_pips} {stepRule().unitLabel})
              </span>
            </div>
          </td>

          {/* 9. R-Multiple */}
          <td class="text-center pos-cell-r">
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

          {/* 10. Quick Actions */}
          <td class="text-right pos-cell-actions">
            <div class="pos-actions-segmented">
              <div class="pos-actions-defensive">
                <button
                  class="btn-pos-action btn-pos-be"
                  onClick={handleMoveToBreakEven}
                  disabled={isSubmitting()}
                  title="Instant 1-Click: Move Stop Loss to Entry Price + Spread Offset"
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

