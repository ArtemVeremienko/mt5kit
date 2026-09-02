import { createSignal, createMemo, createRoot } from 'solid-js';
import { accountStore } from './accountStore';

function createPreferences() {
  const savedWcStr = localStorage.getItem('mt5_risk_working_capital');
  const initialSavedWc =
    savedWcStr !== null && !isNaN(parseFloat(savedWcStr)) && parseFloat(savedWcStr) > 0
      ? parseFloat(savedWcStr)
      : null;

  const [customWorkingCapital, setCustomWorkingCapital] = createSignal<number | null>(initialSavedWc);

  const workingCapital = createMemo<number>(() => {
    const custom = customWorkingCapital();
    if (custom !== null && custom > 0) {
      return custom;
    }
    const bal = accountStore.account().balance;
    if (bal !== undefined && bal !== null && bal > 0) {
      return bal;
    }
    return 100.0;
  });

  const isWorkingCapitalCustom = createMemo<boolean>(() => {
    return customWorkingCapital() !== null;
  });

  const setWorkingCapital = (val: number) => {
    if (!isNaN(val) && val > 0) {
      setCustomWorkingCapital(val);
      localStorage.setItem('mt5_risk_working_capital', val.toString());
    }
  };

  const resetWorkingCapital = () => {
    localStorage.removeItem('mt5_risk_working_capital');
    setCustomWorkingCapital(null);
  };

  const rawRiskMethod = localStorage.getItem('mt5_risk_method') || 'fractional';
  const initialRiskMethod = rawRiskMethod === 'kelly_half' ? 'kelly_half' : 'fractional';
  const [riskMethod, setRiskMethodSignal] = createSignal<string>(initialRiskMethod);

  const [customRiskPct, setCustomRiskPctSignal] = createSignal<number>(
    parseFloat(localStorage.getItem('mt5_risk_custom_pct') || '1.0') || 1.0
  );
  const [minRiskFloorPct, setMinRiskFloorPctSignal] = createSignal<number>(
    parseFloat(localStorage.getItem('mt5_min_risk_floor') || '0.25') || 0.25
  );
  const [maxRiskCeilingPct, setMaxRiskCeilingPctSignal] = createSignal<number>(
    parseFloat(localStorage.getItem('mt5_max_risk_ceiling') || '2.50') || 2.50
  );

  const setMinRiskFloorPct = (val: number) => {
    if (!isNaN(val) && val > 0) {
      setMinRiskFloorPctSignal(val);
      localStorage.setItem('mt5_min_risk_floor', val.toString());
    }
  };

  const setMaxRiskCeilingPct = (val: number) => {
    if (!isNaN(val) && val > 0) {
      setMaxRiskCeilingPctSignal(val);
      localStorage.setItem('mt5_max_risk_ceiling', val.toString());
    }
  };

  const [slMode, setSlModeSignal] = createSignal<string>(
    localStorage.getItem('mt5_risk_sl_mode') || '1/4 ADR'
  );
  const [rrRatio, setRrRatioSignal] = createSignal<number>(
    parseFloat(localStorage.getItem('mt5_risk_rr_ratio') || '1.5') || 1.5
  );
  const [turboMode, setTurboModeSignal] = createSignal<boolean>(
    localStorage.getItem('mt5_turbo_mode') === 'true'
  );
  const [oneClickEnabled, setOneClickEnabledSignal] = createSignal<boolean>(
    localStorage.getItem('mt5_risk_one_click') === 'true'
  );
  const [activeView, setActiveViewSignal] = createSignal<'matrix' | 'positions'>(
    (localStorage.getItem('mt5_active_view') as 'matrix' | 'positions') || 'matrix'
  );

  const setActiveView = (view: 'matrix' | 'positions') => {
    setActiveViewSignal(view);
    localStorage.setItem('mt5_active_view', view);
  };

  const [showStatsBanner, setShowStatsBannerSignal] = createSignal<boolean>(
    localStorage.getItem('mt5_show_stats_banner') === 'true'
  );
  const [pinnedSymbols, setPinnedSymbolsSignal] = createSignal<string[]>(
    JSON.parse(localStorage.getItem('mt5_pinned_symbols') || '[]')
  );
  const [customOrder, setCustomOrderSignal] = createSignal<string[]>(
    JSON.parse(localStorage.getItem('mt5_custom_symbol_order') || '[]')
  );
  const [defaultSltpFocusField, setDefaultSltpFocusFieldSignal] = createSignal<'price' | 'pips' | 'cash'>(
    (localStorage.getItem('mt5_sltp_default_focus') as 'price' | 'pips' | 'cash') || 'price'
  );
  const [slOverrides, setSlOverridesSignal] = createSignal<Record<string, number>>({});

  const setDefaultSltpFocusField = (val: 'price' | 'pips' | 'cash') => {
    setDefaultSltpFocusFieldSignal(val);
    localStorage.setItem('mt5_sltp_default_focus', val);
  };

  const setRiskMethod = (val: string) => {
    setRiskMethodSignal(val);
    localStorage.setItem('mt5_risk_method', val);
  };

  const setCustomRiskPct = (val: number) => {
    setCustomRiskPctSignal(val);
    localStorage.setItem('mt5_risk_custom_pct', val.toString());
  };

  const setSlMode = (val: string) => {
    setSlModeSignal(val);
    localStorage.setItem('mt5_risk_sl_mode', val);
  };

  const setRrRatio = (val: number) => {
    setRrRatioSignal(val);
    localStorage.setItem('mt5_risk_rr_ratio', val.toString());
  };

  const toggleTurboMode = () => {
    const next = !turboMode();
    setTurboModeSignal(next);
    localStorage.setItem('mt5_turbo_mode', next ? 'true' : 'false');
    return next;
  };

  const toggleOneClick = () => {
    const next = !oneClickEnabled();
    setOneClickEnabledSignal(next);
    localStorage.setItem('mt5_risk_one_click', next ? 'true' : 'false');
  };

  const toggleStatsBanner = () => {
    const next = !showStatsBanner();
    setShowStatsBannerSignal(next);
    localStorage.setItem('mt5_show_stats_banner', next ? 'true' : 'false');
  };

  const togglePin = (symbol: string) => {
    const current = pinnedSymbols();
    let updated: string[];
    if (current.includes(symbol)) {
      updated = current.filter((s) => s !== symbol);
    } else {
      updated = [...current, symbol];
    }
    setPinnedSymbolsSignal(updated);
    localStorage.setItem('mt5_pinned_symbols', JSON.stringify(updated));
  };

  const isPinned = (symbol: string) => pinnedSymbols().includes(symbol);

  const setCustomOrder = (order: string[]) => {
    setCustomOrderSignal(order);
    localStorage.setItem('mt5_custom_symbol_order', JSON.stringify(order));
  };

  const resetCustomOrder = () => {
    setCustomOrderSignal([]);
    setPinnedSymbolsSignal([]);
    localStorage.removeItem('mt5_custom_symbol_order');
    localStorage.removeItem('mt5_pinned_symbols');
  };

  const setSymbolSL = (symbol: string, pips: number) => {
    setSlOverridesSignal((prev) => ({ ...prev, [symbol]: pips }));
  };

  const resetSymbolSL = (symbol: string) => {
    setSlOverridesSignal((prev) => {
      const next = { ...prev };
      delete next[symbol];
      return next;
    });
  };

  return {
    workingCapital,
    isWorkingCapitalCustom,
    setWorkingCapital,
    resetWorkingCapital,
    riskMethod,
    setRiskMethod,
    customRiskPct,
    setCustomRiskPct,
    minRiskFloorPct,
    setMinRiskFloorPct,
    maxRiskCeilingPct,
    setMaxRiskCeilingPct,
    slMode,
    setSlMode,
    rrRatio,
    setRrRatio,
    turboMode,
    toggleTurboMode,
    oneClickEnabled,
    toggleOneClick,
    activeView,
    setActiveView,
    showStatsBanner,
    toggleStatsBanner,
    pinnedSymbols,
    togglePin,
    isPinned,
    customOrder,
    setCustomOrder,
    resetCustomOrder,
    defaultSltpFocusField,
    setDefaultSltpFocusField,
    slOverrides,
    setSymbolSL,
    resetSymbolSL,
  };
}

export const preferencesStore = createRoot(createPreferences);
