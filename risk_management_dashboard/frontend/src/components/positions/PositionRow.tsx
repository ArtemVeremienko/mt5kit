import { Component, createSignal, createMemo, createEffect, onCleanup, Show } from 'solid-js';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';
import { positionsStore } from '../../stores/positionsStore';
import { marketStore } from '../../stores/marketStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { formatCurrency } from '../../utils/formatters';
import { getAssetStepRule, stepPrice } from '../../utils/stepperEngine';
import { autofocus } from '../../directives/autofocus';

// Reference directive for compiler JSX recognition
false && autofocus;

interface Props {
  ticket: number;
}

export const PositionRow: Component<Props> = (props) => {
  const position = createMemo(() => positionsStore.getPosition(props.ticket));

  let hubRef: HTMLDivElement | undefined;

  // 3-Tier State Signals for SL
  const [slPrice, setSlPrice] = createSignal<string>('');
  const [slPips, setSlPips] = createSignal<string>('');
  const [slCash, setSlCash] = createSignal<string>('');

  // 3-Tier State Signals for TP
  const [tpPrice, setTpPrice] = createSignal<string>('');
  const [tpPips, setTpPips] = createSignal<string>('');
  const [tpCash, setTpCash] = createSignal<string>('');

  const [isEditing, setIsEditing] = createSignal<boolean>(false);
  const [isSubmitting, setIsSubmitting] = createSignal<boolean>(false);

  const stepRule = createMemo(() => {
    const p = position();
    if (!p) return getAssetStepRule('EURUSD', 5);
    return getAssetStepRule(p.symbol, p.digits, p.pip_size, p.step_rule);
  });

  // Bidirectional SL Calculations
  const updateSlFromPrice = (priceVal: string | number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const num = typeof priceVal === 'string' ? parseFloat(priceVal) : priceVal;

    if (isNaN(num) || num <= 0) {
      setSlPrice(typeof priceVal === 'string' ? priceVal : '');
      setSlPips('');
      setSlCash('');
      return;
    }

    const isBuy = p.type === 'BUY';
    const diff = isBuy ? p.price_open - num : num - p.price_open;
    const pips = diff / rule.pipSize;
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollar = pips * p.volume * pipVal;

    setSlPrice(typeof priceVal === 'string' ? priceVal : num.toFixed(p.digits));
    setSlPips(Math.abs(pips).toFixed(1));
    setSlCash((-Math.abs(dollar)).toFixed(2));
  };

  const updateSlFromPips = (pipsVal: string | number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const num = typeof pipsVal === 'string' ? parseFloat(pipsVal) : pipsVal;

    if (isNaN(num) || num <= 0) {
      setSlPips(typeof pipsVal === 'string' ? pipsVal : '');
      setSlPrice('');
      setSlCash('');
      return;
    }

    const isBuy = p.type === 'BUY';
    const targetPrice = isBuy
      ? p.price_open - num * rule.pipSize
      : p.price_open + num * rule.pipSize;

    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollar = num * p.volume * pipVal;

    setSlPips(typeof pipsVal === 'string' ? pipsVal : num.toFixed(1));
    setSlPrice(Math.max(0, targetPrice).toFixed(p.digits));
    setSlCash((-dollar).toFixed(2));
  };

  const updateSlFromCash = (cashVal: string | number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const num = typeof cashVal === 'string' ? parseFloat(cashVal) : cashVal;
    if (isNaN(num) || num === 0) {
      setSlCash(typeof cashVal === 'string' ? cashVal : '');
      setSlPips('');
      setSlPrice('');
      return;
    }

    const absCash = Math.abs(num);
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const pips = absCash / (p.volume * pipVal);
    const isBuy = p.type === 'BUY';
    const targetPrice = isBuy
      ? p.price_open - pips * rule.pipSize
      : p.price_open + pips * rule.pipSize;

    setSlCash(typeof cashVal === 'string' ? cashVal : (-absCash).toFixed(2));
    setSlPips(pips.toFixed(1));
    setSlPrice(Math.max(0, targetPrice).toFixed(p.digits));
  };

  // Bidirectional TP Calculations
  const updateTpFromPrice = (priceVal: string | number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const num = typeof priceVal === 'string' ? parseFloat(priceVal) : priceVal;

    if (isNaN(num) || num <= 0) {
      setTpPrice(typeof priceVal === 'string' ? priceVal : '');
      setTpPips('');
      setTpCash('');
      return;
    }

    const isBuy = p.type === 'BUY';
    const diff = isBuy ? num - p.price_open : p.price_open - num;
    const pips = diff / rule.pipSize;
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollar = pips * p.volume * pipVal;

    setTpPrice(typeof priceVal === 'string' ? priceVal : num.toFixed(p.digits));
    setTpPips(Math.abs(pips).toFixed(1));
    setTpCash((+Math.abs(dollar)).toFixed(2));
  };

  const updateTpFromPips = (pipsVal: string | number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const num = typeof pipsVal === 'string' ? parseFloat(pipsVal) : pipsVal;

    if (isNaN(num) || num <= 0) {
      setTpPips(typeof pipsVal === 'string' ? pipsVal : '');
      setTpPrice('');
      setTpCash('');
      return;
    }

    const isBuy = p.type === 'BUY';
    const targetPrice = isBuy
      ? p.price_open + num * rule.pipSize
      : p.price_open - num * rule.pipSize;

    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const dollar = num * p.volume * pipVal;

    setTpPips(typeof pipsVal === 'string' ? pipsVal : num.toFixed(1));
    setTpPrice(Math.max(0, targetPrice).toFixed(p.digits));
    setTpCash((+dollar).toFixed(2));
  };

  const updateTpFromCash = (cashVal: string | number) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const num = typeof cashVal === 'string' ? parseFloat(cashVal) : cashVal;
    if (isNaN(num) || num === 0) {
      setTpCash(typeof cashVal === 'string' ? cashVal : '');
      setTpPips('');
      setTpPrice('');
      return;
    }

    const absCash = Math.abs(num);
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const pipVal = calcResult?.calc?.pip_value_per_lot || 10.0;
    const pips = absCash / (p.volume * pipVal);
    const isBuy = p.type === 'BUY';
    const targetPrice = isBuy
      ? p.price_open + pips * rule.pipSize
      : p.price_open - pips * rule.pipSize;

    setTpCash(typeof cashVal === 'string' ? cashVal : (+absCash).toFixed(2));
    setTpPips(pips.toFixed(1));
    setTpPrice(Math.max(0, targetPrice).toFixed(p.digits));
  };

  const [editingSide, setEditingSide] = createSignal<'SL' | 'TP'>('SL');

  // Start Editing with User Focus Preference
  const startEditing = (columnSide: 'SL' | 'TP' = 'SL') => {
    const p = position();
    if (p) {
      if (p.sl && p.sl > 0) {
        updateSlFromPrice(p.sl);
      } else {
        setSlPrice('');
        setSlPips('');
        setSlCash('');
      }

      if (p.tp && p.tp > 0) {
        updateTpFromPrice(p.tp);
      } else {
        setTpPrice('');
        setTpPips('');
        setTpCash('');
      }

      setEditingSide(columnSide);
      setIsEditing(true);
    }
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  // Global Escape, Enter, Click Outside Listener
  createEffect(() => {
    if (!isEditing()) return;

    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        cancelEditing();
      } else if (e.key === 'Enter') {
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

  // Stepper Handlers for SL
  const stepSlPriceHandler = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const currentVal = slPrice().trim() ? parseFloat(slPrice()) : (p.sl || p.price_open);
    const newVal = stepPrice(currentVal, direction, rule, e);
    updateSlFromPrice(newVal);
  };

  const stepSlPipsHandler = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const current = slPips().trim() ? parseFloat(slPips()) : 20.0;
    let step = 1.0;
    if (e) {
      if (e.shiftKey) step = 10.0;
      else if (e.altKey) step = 0.1;
    }
    const next = direction === 'UP' ? current + step : Math.max(0.1, current - step);
    updateSlFromPips(next);
  };

  const stepSlCashHandler = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const current = slCash().trim() ? Math.abs(parseFloat(slCash())) : 50.0;
    let step = 10.0;
    if (e) {
      if (e.shiftKey) step = 50.0;
      else if (e.altKey) step = 1.0;
    }
    const next = direction === 'UP' ? current + step : Math.max(1.0, current - step);
    updateSlFromCash(-next);
  };

  // Stepper Handlers for TP
  const stepTpPriceHandler = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const p = position();
    if (!p) return;
    const rule = stepRule();
    const currentVal = tpPrice().trim() ? parseFloat(tpPrice()) : (p.tp || p.price_open);
    const newVal = stepPrice(currentVal, direction, rule, e);
    updateTpFromPrice(newVal);
  };

  const stepTpPipsHandler = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const current = tpPips().trim() ? parseFloat(tpPips()) : 30.0;
    let step = 1.0;
    if (e) {
      if (e.shiftKey) step = 10.0;
      else if (e.altKey) step = 0.1;
    }
    const next = direction === 'UP' ? current + step : Math.max(0.1, current - step);
    updateTpFromPips(next);
  };

  const stepTpCashHandler = (direction: 'UP' | 'DOWN', e?: KeyboardEvent | MouseEvent) => {
    const current = tpCash().trim() ? Math.abs(parseFloat(tpCash())) : 100.0;
    let step = 10.0;
    if (e) {
      if (e.shiftKey) step = 50.0;
      else if (e.altKey) step = 1.0;
    }
    const next = direction === 'UP' ? current + step : Math.max(1.0, current - step);
    updateTpFromCash(next);
  };

  // Preset Handlers
  const applyBreakEvenSnap = () => {
    const p = position();
    if (!p) return;
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const spreadPips = calcResult?.spec?.spread_pips || 0.5;
    const bufferPips = spreadPips + 0.5;
    updateSlFromPips(bufferPips);
  };

  const applyAdrSlSnap = (fraction: number) => {
    const p = position();
    if (!p) return;
    const calcResult = marketStore.getCalculatedResult(p.symbol);
    const adrPips = calcResult?.spec?.adr_14_pips || 0;
    const slDistPips = adrPips > 0 ? adrPips * fraction : 15.0;
    updateSlFromPips(slDistPips);
  };

  const applyRrSnap = (ratio: number) => {
    const p = position();
    if (!p) return;
    const currentSlPip = slPips().trim() ? parseFloat(slPips()) : 15.0;
    const tpDist = currentSlPip * ratio;
    updateTpFromPips(tpDist);
  };

  // Row Displays
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
      const slNum = slPrice().trim() ? parseFloat(slPrice()) : 0;
      const tpNum = tpPrice().trim() ? parseFloat(tpPrice()) : 0;
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
          <td
            class="text-center pos-cell-sl"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => startEditing('SL')}
          >
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
          <td
            class="text-center pos-cell-tp"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => startEditing('TP')}
          >
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
              <div
                class="sltp-edit-hub"
                ref={hubRef}
                onMouseDown={(e) => e.stopPropagation()}
                onClick={(e) => e.stopPropagation()}
              >
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

                {/* CSS Grid Body: 2 Columns (SL and TP) */}
                <div class="sltp-hub-grid">
                  {/* Left Column: Stop Loss Stacked Tier */}
                  <div class="sltp-hub-column sl-column">
                    <div class="sltp-column-header">
                      <label class="sltp-field-label sl-label">Stop Loss</label>
                      <span class="sltp-sub-hint">Risk Ceiling</span>
                    </div>

                    <div class="sltp-tier-stack">
                      {/* Tier 1: Price */}
                      <div class="sltp-tier-row">
                        <span class="sltp-tier-label">Price</span>
                        <div class="sltp-stepper-box">
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepSlPriceHandler('DOWN', e)}
                            title={`-1 ${stepRule().unitLabel} (Shift: -10, Alt: -0.1)`}
                            tabindex="-1"
                          >
                            −
                          </button>
                          <input
                            use:autofocus={editingSide() === 'SL' && preferencesStore.defaultSltpFocusField() === 'price'}
                            type="number"
                            class="sltp-input-main tabular-num"
                            placeholder="SL Price"
                            min="0"
                            step={stepRule().normalStep}
                            value={slPrice()}
                            onFocus={(e) => e.currentTarget.select()}
                            onBlur={() => {
                              const num = parseFloat(slPrice());
                              const p = position();
                              if (!isNaN(num) && num > 0 && p) setSlPrice(num.toFixed(p.digits));
                            }}
                            onInput={(e) => updateSlFromPrice(e.currentTarget.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'ArrowUp') {
                                e.preventDefault();
                                stepSlPriceHandler('UP', e);
                              } else if (e.key === 'ArrowDown') {
                                e.preventDefault();
                                stepSlPriceHandler('DOWN', e);
                              }
                            }}
                          />
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepSlPriceHandler('UP', e)}
                            title={`+1 ${stepRule().unitLabel} (Shift: +10, Alt: +0.1)`}
                            tabindex="-1"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Tier 2: Pips */}
                      <div class="sltp-tier-row">
                        <span class="sltp-tier-label">Pips</span>
                        <div class="sltp-stepper-box">
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepSlPipsHandler('DOWN', e)}
                            title="-1.0 pip (Shift: -10, Alt: -0.1)"
                            tabindex="-1"
                          >
                            −
                          </button>
                          <input
                            use:autofocus={editingSide() === 'SL' && preferencesStore.defaultSltpFocusField() === 'pips'}
                            type="number"
                            class="sltp-input-main tabular-num"
                            placeholder="Pips"
                            min="0"
                            step="0.1"
                            value={slPips()}
                            onFocus={(e) => e.currentTarget.select()}
                            onBlur={() => {
                              const num = parseFloat(slPips());
                              if (!isNaN(num) && num > 0) setSlPips(num.toFixed(1));
                            }}
                            onInput={(e) => updateSlFromPips(e.currentTarget.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'ArrowUp') {
                                e.preventDefault();
                                stepSlPipsHandler('UP', e);
                              } else if (e.key === 'ArrowDown') {
                                e.preventDefault();
                                stepSlPipsHandler('DOWN', e);
                              }
                            }}
                          />
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepSlPipsHandler('UP', e)}
                            title="+1.0 pip (Shift: +10, Alt: +0.1)"
                            tabindex="-1"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Tier 3: Cash Loss $ */}
                      <div class="sltp-tier-row">
                        <span class="sltp-tier-label">Loss $</span>
                        <div class="sltp-stepper-box">
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepSlCashHandler('DOWN', e)}
                            title="-$10.00 (Shift: -$50, Alt: -$1)"
                            tabindex="-1"
                          >
                            −
                          </button>
                          <input
                            use:autofocus={editingSide() === 'SL' && preferencesStore.defaultSltpFocusField() === 'cash'}
                            type="number"
                            class="sltp-input-main text-risk tabular-num"
                            placeholder="-$ Loss"
                            step="1"
                            value={slCash()}
                            onFocus={(e) => e.currentTarget.select()}
                            onBlur={() => {
                              const num = parseFloat(slCash());
                              if (!isNaN(num) && num !== 0) setSlCash((-Math.abs(num)).toFixed(2));
                            }}
                            onInput={(e) => updateSlFromCash(e.currentTarget.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'ArrowUp') {
                                e.preventDefault();
                                stepSlCashHandler('UP', e);
                              } else if (e.key === 'ArrowDown') {
                                e.preventDefault();
                                stepSlCashHandler('DOWN', e);
                              }
                            }}
                          />
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepSlCashHandler('UP', e)}
                            title="+$10.00 (Shift: +$50, Alt: +$1)"
                            tabindex="-1"
                          >
                            +
                          </button>
                        </div>
                      </div>
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

                  {/* Right Column: Take Profit Stacked Tier */}
                  <div class="sltp-hub-column tp-column">
                    <div class="sltp-column-header">
                      <label class="sltp-field-label tp-label">Take Profit</label>
                      <span class="sltp-sub-hint">Target Objective</span>
                    </div>

                    <div class="sltp-tier-stack">
                      {/* Tier 1: Price */}
                      <div class="sltp-tier-row">
                        <span class="sltp-tier-label">Price</span>
                        <div class="sltp-stepper-box">
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepTpPriceHandler('DOWN', e)}
                            title={`-1 ${stepRule().unitLabel} (Shift: -10, Alt: -0.1)`}
                            tabindex="-1"
                          >
                            −
                          </button>
                          <input
                            use:autofocus={editingSide() === 'TP' && preferencesStore.defaultSltpFocusField() === 'price'}
                            type="number"
                            class="sltp-input-main tabular-num"
                            placeholder="TP Price"
                            min="0"
                            step={stepRule().normalStep}
                            value={tpPrice()}
                            onFocus={(e) => e.currentTarget.select()}
                            onBlur={() => {
                              const num = parseFloat(tpPrice());
                              const p = position();
                              if (!isNaN(num) && num > 0 && p) setTpPrice(num.toFixed(p.digits));
                            }}
                            onInput={(e) => updateTpFromPrice(e.currentTarget.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'ArrowUp') {
                                e.preventDefault();
                                stepTpPriceHandler('UP', e);
                              } else if (e.key === 'ArrowDown') {
                                e.preventDefault();
                                stepTpPriceHandler('DOWN', e);
                              }
                            }}
                          />
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepTpPriceHandler('UP', e)}
                            title={`+1 ${stepRule().unitLabel} (Shift: +10, Alt: +0.1)`}
                            tabindex="-1"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Tier 2: Pips */}
                      <div class="sltp-tier-row">
                        <span class="sltp-tier-label">Pips</span>
                        <div class="sltp-stepper-box">
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepTpPipsHandler('DOWN', e)}
                            title="-1.0 pip (Shift: -10, Alt: -0.1)"
                            tabindex="-1"
                          >
                            −
                          </button>
                          <input
                            use:autofocus={editingSide() === 'TP' && preferencesStore.defaultSltpFocusField() === 'pips'}
                            type="number"
                            class="sltp-input-main tabular-num"
                            placeholder="Pips"
                            min="0"
                            step="0.1"
                            value={tpPips()}
                            onFocus={(e) => e.currentTarget.select()}
                            onBlur={() => {
                              const num = parseFloat(tpPips());
                              if (!isNaN(num) && num > 0) setTpPips(num.toFixed(1));
                            }}
                            onInput={(e) => updateTpFromPips(e.currentTarget.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'ArrowUp') {
                                e.preventDefault();
                                stepTpPipsHandler('UP', e);
                              } else if (e.key === 'ArrowDown') {
                                e.preventDefault();
                                stepTpPipsHandler('DOWN', e);
                              }
                            }}
                          />
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepTpPipsHandler('UP', e)}
                            title="+1.0 pip (Shift: +10, Alt: +0.1)"
                            tabindex="-1"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Tier 3: Cash Gain $ */}
                      <div class="sltp-tier-row">
                        <span class="sltp-tier-label">Profit $</span>
                        <div class="sltp-stepper-box">
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepTpCashHandler('DOWN', e)}
                            title="-$10.00 (Shift: -$50, Alt: -$1)"
                            tabindex="-1"
                          >
                            −
                          </button>
                          <input
                            use:autofocus={editingSide() === 'TP' && preferencesStore.defaultSltpFocusField() === 'cash'}
                            type="number"
                            class="sltp-input-main text-profit tabular-num"
                            placeholder="+$ Profit"
                            step="1"
                            value={tpCash()}
                            onFocus={(e) => e.currentTarget.select()}
                            onBlur={() => {
                              const num = parseFloat(tpCash());
                              if (!isNaN(num) && num !== 0) setTpCash((+Math.abs(num)).toFixed(2));
                            }}
                            onInput={(e) => updateTpFromCash(e.currentTarget.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'ArrowUp') {
                                e.preventDefault();
                                stepTpCashHandler('UP', e);
                              } else if (e.key === 'ArrowDown') {
                                e.preventDefault();
                                stepTpCashHandler('DOWN', e);
                              }
                            }}
                          />
                          <button
                            type="button"
                            class="btn-stepper-touch"
                            onClick={(e) => stepTpCashHandler('UP', e)}
                            title="+$10.00 (Shift: +$50, Alt: +$1)"
                            tabindex="-1"
                          >
                            +
                          </button>
                        </div>
                      </div>
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

