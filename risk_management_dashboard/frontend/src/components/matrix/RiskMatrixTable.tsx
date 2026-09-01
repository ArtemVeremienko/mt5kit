import { Component, For, Show } from 'solid-js';
import { marketStore } from '../../stores/marketStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { SymbolRow } from './SymbolRow';
import { CalculatedSymbolResult } from '../../types';

interface Props {
  onTradeClick: (item: CalculatedSymbolResult, action: 'BUY' | 'SELL') => void;
  onOpenDeepDive: (item: CalculatedSymbolResult) => void;
}

export const RiskMatrixTable: Component<Props> = (props) => {
  const symbols = marketStore.filteredSymbols;
  const categories = marketStore.categories;
  const counts = marketStore.categoryCounts;

  const isCustomStateActive = () =>
    preferencesStore.customOrder().length > 0 ||
    preferencesStore.pinnedSymbols().length > 0 ||
    marketStore.sortCol() !== null;

  return (
    <div class="matrix-section">
      <div class="matrix-toolbar">
        <div class="category-tabs">
          <For each={categories}>
            {(cat) => (
              <button
                class="category-tab-btn"
                classList={{ active: marketStore.activeCategory() === cat }}
                onClick={() => marketStore.setActiveCategory(cat)}
              >
                <span>{cat}</span>
                <span class="tab-badge">{counts()[cat] || 0}</span>
              </button>
            )}
          </For>
        </div>

        <div class="toolbar-right">
          <Show when={isCustomStateActive()}>
            <button
              class="btn-reset-order"
              onClick={() => {
                preferencesStore.resetCustomOrder();
                marketStore.toggleSort(null);
              }}
              title="Reset custom drag order, unpin all symbols, and return to default Market Watch order"
            >
              ↺ Reset Order
            </button>
          </Show>

          <div class="search-box">
            <span class="search-icon">🔍</span>
            <input
              type="text"
              class="search-input"
              placeholder="Search symbol..."
              value={marketStore.searchQuery()}
              onInput={(e) => marketStore.setSearchQuery(e.currentTarget.value)}
            />
          </div>
        </div>
      </div>

      <div class="table-card">
        <div class="table-responsive">
          <table class="risk-matrix-table">
            <thead>
              <tr>
                <th onClick={() => marketStore.toggleSort('symbol')} class="cursor-pointer">
                  Symbol <span class="sort-icon">{marketStore.sortIcon('symbol')}</span>
                </th>
                <th onClick={() => marketStore.toggleSort('bid')} class="cursor-pointer">
                  Market Price <span class="sort-icon">{marketStore.sortIcon('bid')}</span>
                </th>
                <th onClick={() => marketStore.toggleSort('spread')} class="cursor-pointer">
                  Spread <span class="sort-icon">{marketStore.sortIcon('spread')}</span>
                </th>
                <th onClick={() => marketStore.toggleSort('adr')} class="cursor-pointer">
                  14D ADR <span class="sort-icon">{marketStore.sortIcon('adr')}</span>
                </th>
                <th>Stop Loss (Pips)</th>
                <th>Pip Value ($)</th>
                <th onClick={() => marketStore.toggleSort('lot')} class="cursor-pointer">
                  Executable Lot <span class="sort-icon">{marketStore.sortIcon('lot')}</span>
                </th>
                <th onClick={() => marketStore.toggleSort('risk_pct')} class="cursor-pointer">
                  Effective Risk <span class="sort-icon">{marketStore.sortIcon('risk_pct')}</span>
                </th>
                <th onClick={() => marketStore.toggleSort('margin')} class="cursor-pointer">
                  Req. Margin / Health <span class="sort-icon">{marketStore.sortIcon('margin')}</span>
                </th>
                <th class="text-center" style={{ 'min-width': '120px' }}>
                  Execute
                </th>
              </tr>
            </thead>
            <tbody>
              <Show
                when={symbols().length > 0}
                fallback={
                  <tr>
                    <td colspan="10" class="empty-table-msg">
                      No matching symbols found in Market Watch.
                    </td>
                  </tr>
                }
              >
                <For each={symbols()}>
                  {(sym) => (
                    <SymbolRow
                      symbol={sym}
                      onTradeClick={props.onTradeClick}
                      onOpenDeepDive={props.onOpenDeepDive}
                    />
                  )}
                </For>
              </Show>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
