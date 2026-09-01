import { Component, For, Show, createMemo, createSignal, createEffect, onCleanup } from 'solid-js';
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

  const [isFilterOpen, setIsFilterOpen] = createSignal<boolean>(false);
  let filterPopRef: HTMLDivElement | undefined;
  let searchInputRef: HTMLInputElement | undefined;

  // Filter out category tabs that have 0 symbols (keep non-empty categories)
  const visibleCategories = createMemo(() =>
    categories.filter((cat) => cat !== 'All' && (counts()[cat] || 0) > 0)
  );

  const isCustomStateActive = () =>
    preferencesStore.customOrder().length > 0 ||
    preferencesStore.pinnedSymbols().length > 0 ||
    marketStore.sortCol() !== null;

  // Auto-focus search input when popover opens
  createEffect(() => {
    if (isFilterOpen()) {
      setTimeout(() => {
        searchInputRef?.focus();
        searchInputRef?.select();
      }, 50);
    }
  });

  // Global Keyboard shortcuts (/ to open and focus search, Escape to close)
  createEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement;
      const isTyping =
        activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.tagName === 'SELECT');

      if (e.key === '/' && !isTyping) {
        e.preventDefault();
        setIsFilterOpen(true);
      } else if (e.key === 'Escape' && isFilterOpen()) {
        setIsFilterOpen(false);
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (filterPopRef && !filterPopRef.contains(e.target as Node)) {
        setIsFilterOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);

    onCleanup(() => {
      window.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    });
  });

  return (
    <div class="matrix-section">
      <div class="table-card">
        <div class="table-responsive">
          <table class="risk-matrix-table">
            <thead>
              <tr>
                {/* AG-Grid Style Symbol Header with Filter Funnel Trigger & Popover */}
                <th class="col-symbol-header" style={{ width: '175px' }}>
                  <div class="col-header-inner">
                    <span
                      class="col-header-title cursor-pointer"
                      onClick={() => marketStore.toggleSort('symbol')}
                      title="Click to sort by Symbol"
                    >
                      Symbol <span class="sort-icon">{marketStore.sortIcon('symbol')}</span>
                    </span>

                    <div class="col-filter-container" ref={filterPopRef}>
                      <button
                        type="button"
                        class="col-filter-btn"
                        classList={{
                          active: marketStore.isFilteringActive(),
                          open: isFilterOpen(),
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setIsFilterOpen(!isFilterOpen());
                        }}
                        title="Filter & Search Symbols (/)"
                      >
                        <svg class="filter-icon-svg" viewBox="0 0 16 16" width="11" height="11" fill="currentColor">
                          <path d="M1.5 2.5a.5.5 0 0 1 .5-.5h12a.5.5 0 0 1 .38.82l-4.88 5.7V13a.5.5 0 0 1-.72.45l-2.5-1.25A.5.5 0 0 1 6 11.75V8.52L1.12 2.82a.5.5 0 0 1-.12-.32z"/>
                        </svg>
                        <Show when={marketStore.isFilteringActive()}>
                          <span class="filter-active-dot" />
                        </Show>
                      </button>

                      {/* Floating AG-Grid Filter Popover */}
                      <Show when={isFilterOpen()}>
                        <div class="ag-grid-filter-popover" onClick={(e) => e.stopPropagation()}>
                          {/* Search Input Box */}
                          <div class="ag-filter-search-box">
                            <span class="ag-filter-search-icon">🔍</span>
                            <input
                              ref={searchInputRef}
                              type="text"
                              class="ag-filter-search-input"
                              placeholder="Search symbol... (/)"
                              value={marketStore.searchQuery()}
                              onInput={(e) => marketStore.setSearchQuery(e.currentTarget.value)}
                            />
                            <Show when={marketStore.searchQuery().length > 0}>
                              <button
                                type="button"
                                class="ag-filter-clear-btn"
                                onClick={() => {
                                  marketStore.setSearchQuery('');
                                  searchInputRef?.focus();
                                }}
                                title="Clear search text"
                              >
                                ✕
                              </button>
                            </Show>
                          </div>

                          <div class="ag-filter-divider" />

                          {/* Multi-Select Category Checklist */}
                          <div class="ag-filter-checkbox-list">
                            <label class="ag-filter-item select-all">
                              <input
                                type="checkbox"
                                checked={marketStore.isAllCategoriesSelected()}
                                onChange={(e) => marketStore.selectAllCategories(e.currentTarget.checked)}
                              />
                              <span class="ag-filter-label">(Select All)</span>
                              <span class="ag-filter-count">{counts()['All'] || 0}</span>
                            </label>

                            <For each={visibleCategories()}>
                              {(cat) => (
                                <label class="ag-filter-item">
                                  <input
                                    type="checkbox"
                                    checked={marketStore.isCategorySelected(cat)}
                                    onChange={() => marketStore.toggleCategory(cat)}
                                  />
                                  <span class="ag-filter-label">{cat}</span>
                                  <span class="ag-filter-count">{counts()[cat] || 0}</span>
                                </label>
                              )}
                            </For>
                          </div>

                          <div class="ag-filter-divider" />

                          {/* Footer Actions */}
                          <div class="ag-filter-footer">
                            <button
                              type="button"
                              class="btn-reset-filter"
                              disabled={!marketStore.isFilteringActive()}
                              onClick={() => marketStore.resetFilters()}
                            >
                              ↺ Reset Filters
                            </button>

                            <Show when={isCustomStateActive()}>
                              <button
                                type="button"
                                class="btn-reset-order-compact"
                                onClick={() => {
                                  preferencesStore.resetCustomOrder();
                                  marketStore.toggleSort(null);
                                }}
                                title="Reset drag order & sort"
                              >
                                ↺ Reset Order
                              </button>
                            </Show>
                          </div>
                        </div>
                      </Show>
                    </div>
                  </div>
                </th>

                <th onClick={() => marketStore.toggleSort('bid')} class="cursor-pointer text-right" style={{ width: '150px' }}>
                  Market Price (Spread) <span class="sort-icon">{marketStore.sortIcon('bid')}</span>
                </th>
                <th onClick={() => marketStore.toggleSort('adr')} class="cursor-pointer text-right" style={{ width: '100px' }}>
                  14D ADR <span class="sort-icon">{marketStore.sortIcon('adr')}</span>
                </th>
                <th class="text-center" style={{ width: '130px' }}>
                  Stop Loss
                </th>
                <th onClick={() => marketStore.toggleSort('lot')} class="cursor-pointer text-right" style={{ width: '120px' }}>
                  Lot Size <span class="sort-icon">{marketStore.sortIcon('lot')}</span>
                </th>
                <th onClick={() => marketStore.toggleSort('risk_pct')} class="cursor-pointer text-right" style={{ width: '160px' }}>
                  Effective Risk (Margin) <span class="sort-icon">{marketStore.sortIcon('risk_pct')}</span>
                </th>
                <th class="text-center" style={{ width: '140px' }}>
                  Execute
                </th>
              </tr>
            </thead>
            <tbody>
              <Show
                when={symbols().length > 0}
                fallback={
                  <tr>
                    <td colspan="7" class="empty-table-cell">
                      <div class="empty-state-card">
                        <span class="empty-state-icon">🔍</span>
                        <div class="empty-state-title">No Symbols Match Current Filter</div>
                        <div class="empty-state-desc">
                          All categories are deselected or search returned zero results.
                        </div>
                        <button
                          type="button"
                          class="btn-reset-filters-hero"
                          onClick={() => marketStore.resetFilters()}
                        >
                          ↺ Reset All Filters & Show Symbols
                        </button>
                      </div>
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
