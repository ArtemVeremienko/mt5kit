import { Component, Show } from 'solid-js';
import { CalculatedSymbolResult } from '../../types';
import { marketStore } from '../../stores/marketStore';
import { preferencesStore } from '../../stores/preferencesStore';

interface Props {
  item: CalculatedSymbolResult;
  onTradeClick: (item: CalculatedSymbolResult, action: 'BUY' | 'SELL') => void;
  onOpenDeepDive: (item: CalculatedSymbolResult) => void;
}

export const SymbolRow: Component<Props> = (props) => {
  const isPinned = () => preferencesStore.isPinned(props.item.spec.symbol);
  const isDragging = () => marketStore.draggedSymbol() === props.item.spec.symbol;
  const isDragOver = () => marketStore.dragOverSymbol() === props.item.spec.symbol;

  return (
    <tr
      class="symbol-row"
      classList={{
        'is-pinned': isPinned(),
        'is-dragging': isDragging(),
        'drag-over': isDragOver(),
      }}
      draggable={true}
      onDragStart={(e) => {
        marketStore.setDraggedSymbol(props.item.spec.symbol);
        e.dataTransfer?.setData('text/plain', props.item.spec.symbol);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (marketStore.draggedSymbol() !== props.item.spec.symbol) {
          marketStore.setDragOverSymbol(props.item.spec.symbol);
        }
      }}
      onDragLeave={() => {
        if (marketStore.dragOverSymbol() === props.item.spec.symbol) {
          marketStore.setDragOverSymbol(null);
        }
      }}
      onDrop={(e) => {
        e.preventDefault();
        marketStore.handleDrop(props.item.spec.symbol);
      }}
      onDragEnd={() => {
        marketStore.setDraggedSymbol(null);
        marketStore.setDragOverSymbol(null);
      }}
    >
      <td>
        <div class="symbol-cell">
          <span class="drag-handle" title="Drag to reorder symbol">⠿</span>
          <button
            class="pin-btn"
            classList={{ pinned: isPinned() }}
            onClick={() => preferencesStore.togglePin(props.item.spec.symbol)}
            title={isPinned() ? 'Pinned to top (Click to unpin)' : 'Pin symbol to top'}
          >
            📌
          </button>
          <span class="symbol-name">{props.item.spec.symbol}</span>
          <span class="category-pill">{props.item.spec.category}</span>
        </div>
      </td>

      <td>
        <div class="price-cell">
          <span class="price-bid">{props.item.spec.bid_display}</span>
          <span class="price-sep">/</span>
          <span class="price-ask">{props.item.spec.ask_display}</span>
        </div>
      </td>

      <td>
        <span class="spread-val">{props.item.spec.spread_display} p</span>
      </td>

      <td>
        <strong class="adr-val">{props.item.spec.adr_display} p</strong>
      </td>

      <td>
        <div class="sl-input-cell">
          <input
            type="number"
            class="sl-input"
            step="1"
            min="1"
            value={
              preferencesStore.slOverrides()[props.item.spec.symbol] !== undefined
                ? preferencesStore.slOverrides()[props.item.spec.symbol]
                : props.item.calc.sl_pips
            }
            onInput={(e) => {
              const val = parseFloat(e.currentTarget.value);
              if (!isNaN(val) && val > 0) {
                preferencesStore.setSymbolSL(props.item.spec.symbol, val);
              }
            }}
          />
          <button
            class="quick-sl-btn"
            title={`Reset to active preset (${preferencesStore.slMode()})`}
            onClick={() => preferencesStore.resetSymbolSL(props.item.spec.symbol)}
          >
            {preferencesStore.slMode()}
          </button>
        </div>
      </td>

      <td>
        <span class="pip-val">${props.item.calc.pip_val_display}</span>
      </td>

      <td>
        <div class="lot-display">
          <div class="executable-lot-row">
            <span class="executable-lot-val">{props.item.calc.lot_display}</span>
            <Show when={props.item.calc.is_clamped_to_min}>
              <span
                class="tooltip-trigger"
                title={`Theoretical lot (${props.item.calc.exact_lot_display}) is below broker min volume (${props.item.calc.min_volume}). Clamped to ${props.item.calc.lot_display} lot, raising effective risk to ${props.item.calc.effective_risk_pct_display}% (Target: ${props.item.calc.target_risk_pct.toFixed(2)}%).`}
              >
                ⚠️
              </span>
            </Show>
            <Show when={props.item.calc.is_clamped_to_max}>
              <span
                class="tooltip-trigger"
                title={`Theoretical lot (${props.item.calc.exact_lot_display}) exceeds broker max volume (${props.item.calc.max_volume}). Capped at ${props.item.calc.lot_display} lot.`}
              >
                ⚠️
              </span>
            </Show>
          </div>
          <div class="exact-lot-sub">Exact: {props.item.calc.exact_lot_display}</div>
        </div>
      </td>

      <td>
        <div class="risk-cell-wrapper">
          <div
            class="risk-amount-tag"
            classList={{
              'risk-elevated':
                props.item.calc.effective_risk_pct > props.item.calc.target_risk_pct * 1.2,
            }}
          >
            {props.item.calc.risk_display}
          </div>
          <button
            class="btn-icon"
            onClick={() => props.onOpenDeepDive(props.item)}
            title="Deep Dive Math & Multi-Model Sizing Comparison"
          >
            🔍
          </button>
        </div>
      </td>

      <td>
        <div class="margin-cell-wrapper">
          <strong class="margin-val">${props.item.calc.required_margin_display}</strong>
          <span
            class="margin-status-pill"
            classList={{
              'margin-exceeded': props.item.calc.is_margin_exceeded,
              'margin-warning': props.item.calc.margin_status === 'warning',
              'margin-healthy': props.item.calc.margin_status === 'healthy',
            }}
          >
            {props.item.calc.is_margin_exceeded ? '🚨 Exceeded' : `${props.item.calc.margin_utilization_display}%`}
          </span>
        </div>
      </td>

      <td class="text-center">
        <div class="trade-btn-group">
          <button
            class="btn-trade btn-buy"
            onClick={() => props.onTradeClick(props.item, 'BUY')}
            title={`BUY ${props.item.calc.lot_display} lot @ Ask ${props.item.spec.ask_display}`}
          >
            BUY
          </button>
          <button
            class="btn-trade btn-sell"
            onClick={() => props.onTradeClick(props.item, 'SELL')}
            title={`SELL ${props.item.calc.lot_display} lot @ Bid ${props.item.spec.bid_display}`}
          >
            SELL
          </button>
        </div>
      </td>
    </tr>
  );
};
