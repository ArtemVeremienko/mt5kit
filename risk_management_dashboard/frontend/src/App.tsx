import { Component, createSignal, onMount, onCleanup, Show } from 'solid-js';
import { HeaderMetricsBar } from './components/header/HeaderMetricsBar';
import { RiskControlsBar } from './components/controls/RiskControlsBar';
import { StrategyStatsBanner } from './components/stats/StrategyStatsBanner';
import { RiskMatrixTable } from './components/matrix/RiskMatrixTable';
import { OrderManagementPanel } from './components/positions/OrderManagementPanel';
import { DeepDiveModal } from './components/modals/DeepDiveModal';
import { ConfirmTradeModal } from './components/modals/ConfirmTradeModal';
import { ManualStatsModal } from './components/modals/ManualStatsModal';
import { CsvUploadModal } from './components/modals/CsvUploadModal';
import { ToastContainer } from './components/toasts/ToastContainer';
import { api } from './services/api';
import { wsService } from './services/websocket';
import { accountStore } from './stores/accountStore';
import { marketStore } from './stores/marketStore';
import { positionsStore } from './stores/positionsStore';
import { preferencesStore } from './stores/preferencesStore';
import { toastStore } from './stores/toastStore';
import { CalculatedSymbolResult } from './types';

export const App: Component = () => {
  const [deepDiveItem, setDeepDiveItem] = createSignal<CalculatedSymbolResult | null>(null);
  const [pendingTrade, setPendingTrade] = createSignal<{ item: CalculatedSymbolResult; action: 'BUY' | 'SELL' } | null>(null);
  const [isManualStatsOpen, setIsManualStatsOpen] = createSignal<boolean>(false);
  const [isCsvUploadOpen, setIsCsvUploadOpen] = createSignal<boolean>(false);
  const [isSubmittingOrder, setIsSubmittingOrder] = createSignal<boolean>(false);

  onMount(async () => {
    try {
      // 1. Initial account fetch
      const acc = await api.fetchAccount();
      accountStore.updateAccount(acc);

      // 2. Initial calculation payload
      const calcData = await api.fetchInitialCalculate({
        working_capital: preferencesStore.workingCapital(),
        deposited_cash: acc.balance || 20.0,
        leverage: acc.leverage || 300.0,
        risk_method: preferencesStore.riskMethod(),
        custom_risk_pct: preferencesStore.customRiskPct(),
        global_sl_mode: preferencesStore.slMode(),
        global_sl_pips: 20.0,
        symbol_sl_overrides: preferencesStore.slOverrides(),
      });

      marketStore.setTradeStats(calcData.trade_stats);
      if (calcData.sample_info) {
        marketStore.setSampleInfo(calcData.sample_info);
      }
      if (calcData.results && calcData.results.length > 0) {
        marketStore.setRawSymbols(calcData.results.map((r) => r.spec));
      }

      // 3. Initial open positions fetch
      const posData = await api.fetchPositions();
      positionsStore.setPositions(posData.positions);
    } catch (e) {
      console.warn('Initial data hydration error:', e);
    }

    // 4. Connect real-time WebSocket stream
    wsService.connect();
  });

  onCleanup(() => {
    wsService.disconnect();
  });

  const handleTradeClick = async (item: CalculatedSymbolResult, action: 'BUY' | 'SELL') => {
    if (preferencesStore.oneClickEnabled()) {
      await executeOrderDirectly(item, action);
    } else {
      setPendingTrade({ item, action });
    }
  };

  const executeOrderDirectly = async (item: CalculatedSymbolResult, action: 'BUY' | 'SELL') => {
    try {
      setIsSubmittingOrder(true);
      const res = await api.executeOrder({
        symbol: item.spec.symbol,
        action: action,
        volume: item.calc.executable_lot,
        sl_pips: item.calc.sl_pips,
        rr_ratio: preferencesStore.rrRatio(),
        comment: 'SolidRiskEngine',
      });

      if (res.success) {
        toastStore.addToast(
          'Order Executed',
          res.message || `Executed ${action} ${item.calc.executable_lot} lot ${item.spec.symbol}`,
          'success'
        );
        setPendingTrade(null);
      } else {
        toastStore.addToast('Execution Failed', res.message, 'error');
      }
    } catch (e: any) {
      toastStore.addToast('Error', e.message || 'Trade submission failed', 'error');
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  return (
    <div class="dashboard-container">
      <HeaderMetricsBar />

      <main class="dashboard-main">
        <RiskControlsBar />

        <StrategyStatsBanner
          onOpenManualModal={() => setIsManualStatsOpen(true)}
          onOpenCsvModal={() => setIsCsvUploadOpen(true)}
        />

        <RiskMatrixTable
          onTradeClick={handleTradeClick}
          onOpenDeepDive={(item) => setDeepDiveItem(item)}
        />

        <OrderManagementPanel />
      </main>

      {/* Modals */}
      <DeepDiveModal
        item={deepDiveItem()}
        onClose={() => setDeepDiveItem(null)}
      />

      <ConfirmTradeModal
        trade={pendingTrade()}
        onConfirm={() => {
          if (pendingTrade()) {
            executeOrderDirectly(pendingTrade()!.item, pendingTrade()!.action);
          }
        }}
        onCancel={() => setPendingTrade(null)}
        isSubmitting={isSubmittingOrder()}
      />

      <Show when={isManualStatsOpen()}>
        <ManualStatsModal
          isOpen={isManualStatsOpen()}
          onClose={() => setIsManualStatsOpen(false)}
        />
      </Show>

      <Show when={isCsvUploadOpen()}>
        <CsvUploadModal
          isOpen={isCsvUploadOpen()}
          onClose={() => setIsCsvUploadOpen(false)}
        />
      </Show>

      {/* Toasts */}
      <ToastContainer />
    </div>
  );
};
