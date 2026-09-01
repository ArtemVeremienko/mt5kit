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

  const activeSL = createMemo<number>(() => {
    const override = preferencesStore.slOverrides()[props.symbol];
    if (override !== undefined && !isNaN(override) && override > 0) {
      return override;
    }
    return item()?.calc.sl_pips || 20.0;
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
    if (!isNaN(val) && val > 0) {
      preferencesStore.setSymbolSL(props.symbol, val);
    }
  };

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
          <td>
            <div class="symbol-cell">
              <span class="drag-handle" title="Drag to reorder symbol">
                ⠿
              </span>
              <button
                class="pin-btn"
                classList={{ pinned: isPinned() }}
                onClick={() => preferencesStore.togglePin(props.symbol)}
                title={isPinned() ? 'Pinned to top (Click to unpin)' : 'Pin symbol to top'}
              >
                📌
              </button>
              <span class="symbol-name">{data().spec.symbol}</span>
              <span class="category-pill">{data().spec.category}</span>
            </div>
          </td>

          <td>
            <div class="price-cell">
              <span class="price-bid">{data().spec.bid_display}</span>
              <span class="price-sep">/</span>
              <span class="price-ask">{data().spec.ask_display}</span>
            </div>
          </td>

          <td>
            <span class="spread-val">{data().spec.spread_display} p</span>
          </td>

          <td>
            <strong class="adr-val">{data().spec.adr_display} p</strong>
          </td>

          <td>
            <div class="sl-input-cell">
              <input
                type="number"
                class="sl-input"
                step="1"
                min="1"
                value={localVal()}
                onFocus={() => setIsFocused(true)}
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
              />
              <Show
                when={preferencesStore.slOverrides()[props.symbol] !== undefined}
                fallback={
                  <span class="text-xs text-muted" title="Active Stop Loss calculation model">
                    ({preferencesStore.slMode()})
                  </span>
                }
              >
                <button
                  class="quick-sl-btn"
                  onClick={() => {
                    preferencesStore.resetSymbolSL(props.symbol);
                    setLocalVal(activeSL().toString());
                  }}
                  title="Reset to global Stop Loss preset"
                >
                  ↺ Reset
                </button>
              </Show>
            </div>
          </td>

          <td>
            <span class="pip-val">${data().calc.pip_val_display}</span>
          </td>

          <td>
            <div class="lot-display">
              <div class="executable-lot-row">
                <span class="executable-lot-val">{data().calc.lot_display}</span>
                <Show when={data().calc.executable_lot !== data().calc.exact_lot}>
                  <span
                    class="tooltip-trigger"
                    title={`Broker Clamped (Exact math: ${data().calc.exact_lot_display} Lot)`}
                  >
                    ⚠️
                  </span>
                </Show>
              </div>
              <span class="exact-lot-sub">({data().calc.exact_lot_display} Lot)</span>
            </div>
          </td>

          <td>
            <div class="risk-cell-wrapper">
              <span
                class="risk-amount-tag"
                classList={{
                  'risk-elevated': data().calc.effective_risk_pct > data().calc.target_risk_pct * 1.05,
                }}
              >
                {data().calc.risk_display}
              </span>
              <button
                class="btn-icon"
                onClick={() => props.onOpenDeepDive(data())}
                title="Deep-dive calculation breakdown & multi-model comparison"
              >
                🔍
              </button>
            </div>
          </td>

          <td>
            <div class="margin-cell-wrapper">
              <span class="margin-val">${data().calc.required_margin_display}</span>
              <span
                class={`margin-status-pill margin-${data().calc.margin_health}`}
                title={`Margin utilization: ${data().calc.margin_utilization_display}%`}
              >
                {data().calc.margin_utilization_display}%
              </span>
            </div>
          </td>

          <td class="text-center">
            <div class="trade-btn-group">
              <button
                class="btn-trade btn-buy"
                onClick={() => props.onTradeClick(data(), 'BUY')}
                title={`Instant BUY ${data().calc.lot_display} Lot ${data().spec.symbol}`}
              >
                BUY
              </button>
              <button
                class="btn-trade btn-sell"
                onClick={() => props.onTradeClick(data(), 'SELL')}
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
