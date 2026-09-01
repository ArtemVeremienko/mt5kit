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
  const [activeCategory, setActiveCategory] = createSignal<string>('All');
  const [searchQuery, setSearchQuery] = createSignal<string>('');
  const [sortCol, setSortCol] = createSignal<SortColumn>(null);
  const [sortDirection, setSortDirection] = createSignal<SortDirection>('none');
  const [selectedItem, setSelectedItem] = createSignal<CalculatedSymbolResult | null>(null);
  const [draggedSymbol, setDraggedSymbol] = createSignal<string | null>(null);
  const [dragOverSymbol, setDragOverSymbol] = createSignal<string | null>(null);

  const categories = ['All', 'Forex Majors', 'Forex Minors', 'Metals', 'Energies', 'Indices', 'Crypto'];

  // Fine-grained calculated results
  const calculatedResults = createMemo<CalculatedSymbolResult[]>(() => {
    const symbols = rawSymbols();
    const wc = preferencesStore.workingCapital();
    const depCash = accountStore.account().balance || 20.0;
    const lev = accountStore.account().leverage || 300.0;
    const method = preferencesStore.riskMethod();
    const customPct = preferencesStore.customRiskPct();
    const slM = preferencesStore.slMode();
    const overrides = preferencesStore.slOverrides();
    const stats = tradeStats();

    return symbols.map((s) =>
      computeLocalRiskForResult(s, wc, depCash, lev, method, customPct, slM, overrides, stats)
    );
  });

  const categoryCounts = createMemo<Record<string, number>>(() => {
    const counts: Record<string, number> = { All: rawSymbols().length };
    rawSymbols().forEach((s) => {
      const cat = s.category || 'Other';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  });

  // Filtered and 3-State Sorted results
  const filteredResults = createMemo<CalculatedSymbolResult[]>(() => {
    const list = calculatedResults().filter((r) => {
      const matchCat = activeCategory() === 'All' || r.spec.category === activeCategory();
      const matchSearch = !searchQuery() || r.spec.symbol.toUpperCase().includes(searchQuery().toUpperCase());
      return matchCat && matchSearch;
    });

    const isPin = (sym: string) => preferencesStore.isPinned(sym);
    const customOrderList = preferencesStore.customOrder();
    const getCustomIndex = (sym: string) => {
      const idx = customOrderList.indexOf(sym);
      return idx !== -1 ? idx : 999999;
    };

    const col = sortCol();
    const dir = sortDirection();

    return list.slice().sort((a, b) => {
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
    calculatedResults,
    categoryCounts,
    filteredResults,
    handleDrop,
  };
}

export const marketStore = createRoot(createMarketStore);
