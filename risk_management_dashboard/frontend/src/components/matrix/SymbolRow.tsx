import { Component, Show, createSignal, createMemo, createEffect } from 'solid-js';
import { CalculatedSymbolResult } from '../../types';
import { marketStore } from '../../stores/marketStore';
import { preferencesStore } from '../../stores/preferencesStore';

interface Props {
  symbol: string;
  onTradeClick: (item: CalculatedSymbolResult, action: 'BUY' | 'SELL') => void;
  onOpenDeepDive: (item: CalculatedSymbolResult) => void;
}

export const SymbolRow: Component<Props> = (props) => {
  const item = createMemo(() => marketStore.getCalculatedResult(props.symbol));

  const isPinned = () => preferencesStore.isPinned(props.symbol);
  const isDragging = () => marketStore.draggedSymbol() === props.symbol;
  const isDragOver = () => marketStore.dragOverSymbol() === props.symbol;
  const defaultSL = createMemo<number>(() => {
    const d = item();
    if (!d) return 20.0;
    const adr14 = d.spec.adr_14_pips || 65.0;
    const atr14 = d.spec.atr_14_pips || adr14 * 1.05;
    const slMode = preferencesStore.slMode();
    if (slMode === '1/4 ADR') return Math.max(1.0, Math.round(adr14 * 0.25 * 10) / 10);
    if (slMode === '1/3 ADR') return Math.max(1.0, Math.round(adr14 * (1.0 / 3.0) * 10) / 10);
    if (slMode === '1/2 ADR') return Math.max(1.0, Math.round(adr14 * 0.5 * 10) / 10);
    if (slMode === '1 ADR') return Math.max(1.0, Math.round(adr14 * 10) / 10);
    if (slMode === '1 ATR') return Math.max(1.0, Math.round(atr14 * 10) / 10);
    return 20.0;
  });

  const activeSL = createMemo<number>(() => {
    const override = preferencesStore.slOverrides()[props.symbol];
    if (override !== undefined && !isNaN(override) && override > 0) {
      return override;
    }
    return defaultSL();
  });

  const isCustomSL = createMemo<boolean>(() => {
    const override = preferencesStore.slOverrides()[props.symbol];
    return override !== undefined && !isNaN(override) && Math.abs(override - defaultSL()) >= 0.0001;
  });

  const [isFocused, setIsFocused] = createSignal(false);
  const [localVal, setLocalVal] = createSignal<string>(activeSL().toString());

  // Sync local input with active SL only when user is NOT actively typing
  createEffect(() => {
    const sl = activeSL();
    if (!isFocused()) {
      setLocalVal(sl.toString());
    }
  });

  const handleSlCommit = (inputStr: string) => {
    const val = parseFloat(inputStr);
    const def = defaultSL();
    if (isNaN(val) || val <= 0 || Math.abs(val - def) < 0.0001) {
      preferencesStore.resetSymbolSL(props.symbol);
      setLocalVal(def.toString());
    } else {
      preferencesStore.setSymbolSL(props.symbol, val);
    }
  };

  // Smart risk alert: only warn if broker lot clamping caused risk to overshoot/undershoot by > 10%
  const isRiskDeviated = createMemo(() => {
    const d = item();
    if (!d) return false;
    const target = d.calc.target_risk_pct || 1.0;
    const effective = d.calc.effective_risk_pct || 1.0;
    return Math.abs(effective - target) / target > 0.10;
  });

  return (
    <Show when={item()}>
      {(data) => (
        <tr
          class="symbol-row"
          classList={{
            'is-pinned': isPinned(),
            'is-dragging': isDragging(),
            'drag-over': isDragOver(),
          }}
          draggable={true}
          onDblClick={() => props.onOpenDeepDive(data())}
          title="Double-click row to open Deep Dive calculation"
          onDragStart={(e) => {
            marketStore.setDraggedSymbol(props.symbol);
            e.dataTransfer?.setData('text/plain', props.symbol);
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (marketStore.draggedSymbol() !== props.symbol) {
              marketStore.setDragOverSymbol(props.symbol);
            }
          }}
          onDragLeave={() => {
            if (marketStore.dragOverSymbol() === props.symbol) {
              marketStore.setDragOverSymbol(null);
            }
          }}
          onDrop={(e) => {
            e.preventDefault();
            marketStore.handleDrop(props.symbol);
          }}
          onDragEnd={() => {
            marketStore.setDraggedSymbol(null);
            marketStore.setDragOverSymbol(null);
          }}
        >
          {/* Col 1: Symbol (with drag handle, pin) */}
          <td>
            <div class="symbol-cell">
              <span class="drag-handle" title="Drag to reorder symbol">
                ⠿
              </span>
              <button
                class="pin-btn"
                classList={{ pinned: isPinned() }}
                onClick={(e) => {
                  e.stopPropagation();
                  preferencesStore.togglePin(props.symbol);
                }}
                title={isPinned() ? 'Pinned to top (Click to unpin)' : 'Pin symbol to top'}
              >
                📌
              </button>
              <span class="symbol-name">{data().spec.symbol}</span>
            </div>
          </td>

          {/* Col 2: Market Price & Spread (Stacked) */}
          <td class="text-right">
            <div class="price-stacked">
              <div class="price-bid-row">
                <span class="price-bid tabular-num">{data().spec.bid_display}</span>
                <span class="spread-pill-mini">{data().spec.spread_display}p</span>
              </div>
              <div class="price-ask-row">
                <span class="price-ask tabular-num">{data().spec.ask_display}</span>
              </div>
            </div>
          </td>

          {/* Col 3: 14D ADR */}
          <td class="text-right">
            <span class="adr-val tabular-num">{data().spec.adr_display} p</span>
          </td>

          {/* Col 4: Stop Loss (Wider 76px numeric input with Auto-Select & Custom Reset) */}
          <td class="text-center">
            <div class="sl-input-cell-wrapper" classList={{ 'is-overridden': isCustomSL() }}>
              <input
                type="number"
                class="sl-input tabular-num"
                classList={{ 'sl-input-custom': isCustomSL() }}
                step="1"
                min="1"
                value={localVal()}
                onFocus={(e) => {
                  setIsFocused(true);
                  e.currentTarget.select(); // Auto-select for instant 1-keystroke replacement
                }}
                onBlur={(e) => {
                  setIsFocused(false);
                  handleSlCommit(e.currentTarget.value);
                }}
                onInput={(e) => {
                  setLocalVal(e.currentTarget.value);
                  handleSlCommit(e.currentTarget.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSlCommit(e.currentTarget.value);
                    e.currentTarget.blur();
                  }
                }}
                title="Stop Loss in Points/Pips (Auto-selects on focus, Enter to commit)"
              />
              <Show when={isCustomSL()}>
                <button
                  class="quick-sl-reset-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    preferencesStore.resetSymbolSL(props.symbol);
                    setLocalVal(activeSL().toString());
                  }}
                  title="Custom SL active — click to reset to global preset"
                >
                  ↺
                </button>
              </Show>
            </div>
          </td>

          {/* Col 5: Lot Size */}
          <td class="text-right">
            <div class="lot-cell-wrapper" title={`Exact calculation: ${data().calc.exact_lot_display} Lot`}>
              <span class="executable-lot-val tabular-num">{data().calc.lot_display} Lot</span>
              <Show when={isRiskDeviated()}>
                <span
                  class="risk-alert-icon"
                  title={`Risk deviation warning: Min/Max broker lot clamp caused effective risk to deviate (${data().calc.risk_display})`}
                >
                  ⚠️
                </span>
              </Show>
            </div>
          </td>

          {/* Col 6: Effective Risk & Required Margin (Stacked) */}
          <td class="text-right">
            <div
              class="risk-stacked-cell"
              onClick={() => props.onOpenDeepDive(data())}
              title="Click to view deep dive analysis"
            >
              <div class="risk-main-row">
                <span
                  class="risk-amount-tag tabular-num"
                  classList={{
                    'risk-elevated': isRiskDeviated(),
                  }}
                >
                  {data().calc.risk_display}
                </span>
              </div>
              <div class="margin-sub-row">
                <span class="margin-sub-text">Margin: ${data().calc.required_margin_display}</span>
              </div>
            </div>
          </td>

          {/* Col 7: Clean Action Execution Buttons */}
          <td class="text-center">
            <div class="trade-btn-group">
              <button
                class="btn-trade btn-buy"
                onClick={(e) => {
                  e.stopPropagation();
                  props.onTradeClick(data(), 'BUY');
                }}
                title={`Instant BUY ${data().calc.lot_display} Lot ${data().spec.symbol}`}
              >
                BUY
              </button>
              <button
                class="btn-trade btn-sell"
                onClick={(e) => {
                  e.stopPropagation();
                  props.onTradeClick(data(), 'SELL');
                }}
                title={`Instant SELL ${data().calc.lot_display} Lot ${data().spec.symbol}`}
              >
                SELL
              </button>
            </div>
          </td>
        </tr>
      )}
    </Show>
  );
};
