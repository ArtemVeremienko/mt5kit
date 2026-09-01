import { createSignal, createRoot, createMemo } from 'solid-js';
import { SymbolSpec, CalculatedSymbolResult, TradeStats, SampleSizeInfo } from '../types';
import { computeLocalRiskForResult } from '../utils/lotCalculator';
import { preferencesStore } from './preferencesStore';
import { accountStore } from './accountStore';

export type SortColumn = 'symbol' | 'bid' | 'spread' | 'adr' | 'lot' | 'risk_pct' | 'margin' | null;
export type SortDirection = 'none' | 'asc' | 'desc';

function createMarketStore() {
  const [rawSymbols, setRawSymbols] = createSignal<SymbolSpec[]>([]);
  const [tradeStats, setTradeStats] = createSignal<Partial<TradeStats>>({});
  const [sampleInfo, setSampleInfo] = createSignal<SampleSizeInfo | undefined>(undefined);
  const [selectedCategories, setSelectedCategories] = createSignal<string[]>([]);
  const [activeCategory, setActiveCategory] = createSignal<string>('All');
  const [searchQuery, setSearchQuery] = createSignal<string>('');
  const [sortCol, setSortCol] = createSignal<SortColumn>(null);
  const [sortDirection, setSortDirection] = createSignal<SortDirection>('none');
  const [selectedItem, setSelectedItem] = createSignal<CalculatedSymbolResult | null>(null);
  const [draggedSymbol, setDraggedSymbol] = createSignal<string | null>(null);
  const [dragOverSymbol, setDragOverSymbol] = createSignal<string | null>(null);

  const categories = ['All', 'Forex Majors', 'Forex Minors', 'Metals', 'Energies', 'Indices', 'Stocks', 'Crypto'];

  // Map of symbol -> CalculatedSymbolResult
  const calculatedResultsMap = createMemo<Map<string, CalculatedSymbolResult>>(() => {
    const symbols = rawSymbols();
    const wc = preferencesStore.workingCapital();
    const depCash = accountStore.account().balance || 20.0;
    const lev = accountStore.account().leverage || 300.0;
    const method = preferencesStore.riskMethod();
    const customPct = preferencesStore.customRiskPct();
    const slM = preferencesStore.slMode();
    const overrides = preferencesStore.slOverrides();
    const stats = tradeStats();

    const map = new Map<string, CalculatedSymbolResult>();
    for (const s of symbols) {
      const res = computeLocalRiskForResult(s, wc, depCash, lev, method, customPct, slM, overrides, stats);
      map.set(s.symbol, res);
    }
    return map;
  });

  const getCalculatedResult = (symbol: string): CalculatedSymbolResult | undefined => {
    return calculatedResultsMap().get(symbol);
  };

  const categoryCounts = createMemo<Record<string, number>>(() => {
    const counts: Record<string, number> = { All: rawSymbols().length };
    rawSymbols().forEach((s) => {
      const cat = s.category || 'Other';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  });

  const isCategorySelected = (cat: string) => {
    const selected = selectedCategories();
    if (selected.length === 0) return true;
    if (selected.includes('__NONE__')) return false;
    return selected.includes(cat);
  };

  const toggleCategory = (cat: string) => {
    const allNonEmpty = Object.keys(categoryCounts()).filter((c) => c !== 'All' && (categoryCounts()[c] || 0) > 0);
    const current =
      selectedCategories().length === 0
        ? [...allNonEmpty]
        : selectedCategories().filter((c) => c !== '__NONE__');

    if (current.includes(cat)) {
      const next = current.filter((c) => c !== cat);
      setSelectedCategories(next.length === 0 ? ['__NONE__'] : next);
    } else {
      const next = [...current, cat];
      if (next.length >= allNonEmpty.length) {
        setSelectedCategories([]); // all
      } else {
        setSelectedCategories(next);
      }
    }
  };

  const selectAllCategories = (selectAll: boolean) => {
    if (selectAll) {
      setSelectedCategories([]);
    } else {
      setSelectedCategories(['__NONE__']);
    }
  };

  const isAllCategoriesSelected = () => {
    const selected = selectedCategories();
    return selected.length === 0;
  };

  const isFilteringActive = createMemo(() => {
    return searchQuery().trim().length > 0 || selectedCategories().length > 0;
  });

  const resetFilters = () => {
    setSearchQuery('');
    setSelectedCategories([]);
    setActiveCategory('All');
  };

  // Filtered and Sorted stable list of symbol strings
  const filteredSymbols = createMemo<string[]>(() => {
    const map = calculatedResultsMap();
    const query = searchQuery().toUpperCase();

    const matching: CalculatedSymbolResult[] = [];
    for (const res of map.values()) {
      const cat = res.spec.category || 'Other';
      const matchCat = isCategorySelected(cat);
      const matchSearch = !query || res.spec.symbol.toUpperCase().includes(query);
      if (matchCat && matchSearch) {
        matching.push(res);
      }
    }

    const isPin = (sym: string) => preferencesStore.isPinned(sym);
    const customOrderList = preferencesStore.customOrder();
    const getCustomIndex = (sym: string) => {
      const idx = customOrderList.indexOf(sym);
      return idx !== -1 ? idx : 999999;
    };

    const col = sortCol();
    const dir = sortDirection();

    matching.sort((a, b) => {
      const pinnedA = isPin(a.spec.symbol);
      const pinnedB = isPin(b.spec.symbol);

      // Pinned symbols always stay at the top
      if (pinnedA && !pinnedB) return -1;
      if (!pinnedA && pinnedB) return 1;

      // Natural MT5 sequence / Custom Drag order when sort is 'none'
      if (!col || dir === 'none') {
        const idxA = getCustomIndex(a.spec.symbol);
        const idxB = getCustomIndex(b.spec.symbol);
        if (idxA !== idxB) return idxA - idxB;
        return 0;
      }

      let valA: string | number = 0;
      let valB: string | number = 0;

      if (col === 'symbol') {
        valA = a.spec.symbol;
        valB = b.spec.symbol;
      } else if (col === 'bid') {
        valA = a.spec.bid;
        valB = b.spec.bid;
      } else if (col === 'spread') {
        valA = a.spec.spread_pips;
        valB = b.spec.spread_pips;
      } else if (col === 'adr') {
        valA = a.spec.adr_14_pips;
        valB = b.spec.adr_14_pips;
      } else if (col === 'lot') {
        valA = a.calc.executable_lot;
        valB = b.calc.executable_lot;
      } else if (col === 'risk_pct') {
        valA = a.calc.effective_risk_pct;
        valB = b.calc.effective_risk_pct;
      } else if (col === 'margin') {
        valA = a.calc.required_margin;
        valB = b.calc.required_margin;
      }

      if (valA < valB) return dir === 'asc' ? -1 : 1;
      if (valA > valB) return dir === 'asc' ? 1 : -1;
      return 0;
    });

    return matching.map((r) => r.spec.symbol);
  });

  const toggleSort = (col: SortColumn) => {
    if (sortCol() !== col) {
      setSortCol(col);
      setSortDirection('asc');
    } else if (sortDirection() === 'asc') {
      setSortDirection('desc');
    } else {
      setSortCol(null);
      setSortDirection('none');
    }
  };

  const sortIcon = (col: SortColumn): string => {
    if (sortCol() !== col || sortDirection() === 'none') return '↕';
    return sortDirection() === 'asc' ? '▲' : '▼';
  };

  const handleDrop = (targetSymbol: string) => {
    const srcSymbol = draggedSymbol();
    if (!srcSymbol || srcSymbol === targetSymbol) {
      setDraggedSymbol(null);
      setDragOverSymbol(null);
      return;
    }

    let currentOrder = [...preferencesStore.customOrder()];
    const allSymbols = rawSymbols().map((s) => s.symbol);
    allSymbols.forEach((sym) => {
      if (!currentOrder.includes(sym)) {
        currentOrder.push(sym);
      }
    });

    const srcIndex = currentOrder.indexOf(srcSymbol);
    const targetIndex = currentOrder.indexOf(targetSymbol);

    if (srcIndex !== -1 && targetIndex !== -1) {
      currentOrder.splice(srcIndex, 1);
      currentOrder.splice(targetIndex, 0, srcSymbol);
      preferencesStore.setCustomOrder(currentOrder);
      setSortCol(null);
      setSortDirection('none');
    }

    setDraggedSymbol(null);
    setDragOverSymbol(null);
  };

  return {
    rawSymbols,
    setRawSymbols,
    tradeStats,
    setTradeStats,
    sampleInfo,
    setSampleInfo,
    activeCategory,
    setActiveCategory,
    searchQuery,
    setSearchQuery,
    sortCol,
    sortDirection,
    toggleSort,
    sortIcon,
    selectedItem,
    setSelectedItem,
    draggedSymbol,
    setDraggedSymbol,
    dragOverSymbol,
    setDragOverSymbol,
    categories,
    calculatedResultsMap,
    getCalculatedResult,
    categoryCounts,
    selectedCategories,
    setSelectedCategories,
    isCategorySelected,
    toggleCategory,
    selectAllCategories,
    isAllCategoriesSelected,
    isFilteringActive,
    resetFilters,
    filteredSymbols,
    handleDrop,
  };
}

export const marketStore = createRoot(createMarketStore);
