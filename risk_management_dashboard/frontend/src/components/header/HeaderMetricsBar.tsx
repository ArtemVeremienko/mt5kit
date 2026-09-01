import { Component, Show, createMemo, createSignal, createEffect, onCleanup } from 'solid-js';
import { accountStore } from '../../stores/accountStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { positionsStore } from '../../stores/positionsStore';
import { marketStore } from '../../stores/marketStore';
import { toastStore } from '../../stores/toastStore';
import { wsService } from '../../services/websocket';
import { formatCurrency } from '../../utils/formatters';

interface Props {
  onOpenRiskModal: () => void;
  onOpenStrategyModal: () => void;
}

export const HeaderMetricsBar: Component<Props> = (props) => {
  const account = accountStore.account;
  const isConnected = accountStore.isConnected;
  const floatingProfit = positionsStore.totalFloatingProfit;
  const posCount = positionsStore.totalPositionsCount;
  const symbolCount = () => marketStore.rawSymbols().length;
  const activeView = preferencesStore.activeView;
  const tradeStats = marketStore.tradeStats;
  const sampleInfo = marketStore.sampleInfo;

  const [isAccountInfoOpen, setIsAccountInfoOpen] = createSignal<boolean>(false);
  let accountInfoRef: HTMLDivElement | undefined;

  // Global Escape & Click-Outside dismissal for Account Info popover
  createEffect(() => {
    if (!isAccountInfoOpen()) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsAccountInfoOpen(false);
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (accountInfoRef && !accountInfoRef.contains(e.target as Node)) {
        setIsAccountInfoOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);

    onCleanup(() => {
      window.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    });
  });

  const handleTurboToggle = () => {
    const isTurbo = preferencesStore.toggleTurboMode();
    wsService.sendRateUpdate(isTurbo ? 500 : 2000);
    toastStore.addToast(
      isTurbo ? '⚡ Turbo Mode Activated' : 'Standard Mode',
      isTurbo ? 'Streaming ticks every 500ms with microsecond reactivity' : 'Streaming ticks every 2.0s',
      'success'
    );
  };

  const handleOneClickToggle = () => {
    preferencesStore.toggleOneClick();
    toastStore.addToast(
      preferencesStore.oneClickEnabled() ? '⚡ One-Click Trading Enabled' : 'One-Click Trading Disabled',
      preferencesStore.oneClickEnabled()
        ? 'Orders will execute immediately upon clicking BUY or SELL'
        : 'Order confirmation modal will appear before execution',
      preferencesStore.oneClickEnabled() ? 'warning' : 'info'
    );
  };

  // Compact Risk summary string
  const riskSummaryText = createMemo(() => {
    const wc = formatCurrency(preferencesStore.workingCapital());
    const method = preferencesStore.riskMethod();
    const customPct = preferencesStore.customRiskPct();
    const sl = preferencesStore.slMode();
    const rr = preferencesStore.rrRatio();
    const stats = tradeStats();

    let targetRisk = `${customPct.toFixed(1)}%`;
    if (method === 'kelly_full') targetRisk = `${((stats.kelly_full ?? 0) * 100).toFixed(1)}% Kelly`;
    else if (method === 'kelly_half') targetRisk = `${((stats.kelly_half ?? 0) * 100).toFixed(1)}% 1/2 Kelly`;
    else if (method === 'kelly_quarter') targetRisk = `${((stats.kelly_quarter ?? 0) * 100).toFixed(1)}% 1/4 Kelly`;
    else if (method === 'optimal_f_full') targetRisk = `${((stats.optimal_f ?? 0) * 100).toFixed(1)}% Opt f`;
    else if (method === 'optimal_f_half') targetRisk = `${((stats.optimal_f_half ?? 0) * 100).toFixed(1)}% 1/2 f`;
    else if (method === 'optimal_f_quarter') targetRisk = `${((stats.optimal_f_quarter ?? 0) * 100).toFixed(1)}% 1/4 f`;

    return `${wc} · ${targetRisk} · ${sl} · 1:${rr} RR`;
  });

  // Compact Strategy summary string
  const strategySummaryText = createMemo(() => {
    const trades = tradeStats().total_trades || 0;
    const wr = ((tradeStats().win_rate || 0) * 100).toFixed(0);
    const pf = (tradeStats().profit_factor || 0).toFixed(2);

    return `${trades} Trades · ${wr}% WR · PF ${pf}`;
  });

  return (
    <header class="dashboard-header">
      {/* Left Zone: Brand Logo & Segmented Workspace Navigation */}
      <div class="header-left-zone">
        <div class="brand-logo" title="MetaTrader 5 Risk Management Engine">
          <span class="logo-icon">⚡</span>
          <div class="brand-title-group">
            <span class="brand-title">MT5 RISK</span>
          </div>
        </div>

        <div class="header-workspace-switcher">
          <button
            class="header-nav-btn"
            classList={{ active: activeView() === 'matrix' }}
            onClick={() => preferencesStore.setActiveView('matrix')}
            title="Market Risk Screener Matrix (Hotkey: 1)"
          >
            <span class="btn-icon">🎯</span>
            <span class="btn-text">Screener</span>
            <span class="btn-badge">{symbolCount()}</span>
            <kbd class="btn-kbd">1</kbd>
          </button>

          <button
            class="header-nav-btn"
            classList={{
              active: activeView() === 'positions',
              'has-orders': posCount() > 0,
            }}
            onClick={() => preferencesStore.setActiveView('positions')}
            title="Live Open Positions Manager (Hotkey: 2)"
          >
            <span class="btn-icon">💼</span>
            <span class="btn-text">Positions</span>
            <span class="btn-badge" classList={{ 'badge-active': posCount() > 0 }}>
              {posCount()}
            </span>
            <Show when={posCount() > 0}>
              <span
                class="header-pnl-tag"
                classList={{
                  'text-profit': floatingProfit() > 0,
                  'text-loss': floatingProfit() < 0,
                }}
              >
                {floatingProfit() >= 0 ? `+${formatCurrency(floatingProfit())}` : formatCurrency(floatingProfit())}
              </span>
            </Show>
            <kbd class="btn-kbd">2</kbd>
          </button>
        </div>
      </div>

      {/* Center Zone: Account Telemetry + Interactive Summary Pills */}
      <div class="header-center-zone">
        <div class="account-inline-metrics-container" ref={accountInfoRef}>
          <div class="account-inline-metrics">
            <div class="metric-mini-group" title="Deposited Balance in Broker Account">
              <span class="metric-mini-label">BAL</span>
              <span class="metric-mini-val font-mono">{formatCurrency(account().balance || 0.0)}</span>
            </div>

            <div class="metric-mini-group" title="Net Real-Time Equity">
              <span class="metric-mini-label">EQ</span>
              <span class="metric-mini-val font-mono">{formatCurrency(account().equity || 0.0)}</span>
            </div>

            <div class="metric-mini-group" title="Floating Profit / Loss">
              <span class="metric-mini-label">P&L</span>
              <span
                class="metric-mini-val font-mono"
                classList={{
                  'text-profit': floatingProfit() > 0,
                  'text-loss': floatingProfit() < 0,
                  'text-neutral': floatingProfit() === 0,
                }}
              >
                {floatingProfit() > 0
                  ? `+${formatCurrency(floatingProfit())}`
                  : floatingProfit() < 0
                  ? formatCurrency(floatingProfit())
                  : '$0.00'}
              </span>
            </div>

            <button
              type="button"
              class="btn-account-info"
              classList={{ active: isAccountInfoOpen() }}
              onClick={() => setIsAccountInfoOpen(!isAccountInfoOpen())}
              title="Click to view full MT5 Account Info (Leverage, Server, Margin Health, Login)"
            >
              <span class="account-info-icon">ℹ️</span>
            </button>
          </div>

          {/* Floating Account Details Popover */}
          <Show when={isAccountInfoOpen()}>
            <div class="account-info-popover">
              <div class="acc-popover-header">
                <div class="acc-popover-title-group">
                  <span class="acc-popover-icon">👤</span>
                  <span class="acc-popover-title">MT5 ACCOUNT TELEMETRY</span>
                </div>
                <span class="acc-popover-badge" classList={{ 'badge-live': isConnected() }}>
                  {isConnected() ? 'MT5 LIVE' : 'OFFLINE'}
                </span>
              </div>

              <div class="acc-popover-grid">
                <div class="acc-popover-item">
                  <span class="acc-popover-label">Login / ID</span>
                  <span class="acc-popover-val font-mono">#{account().login || '—'}</span>
                </div>
                <div class="acc-popover-item">
                  <span class="acc-popover-label">Account Name</span>
                  <span class="acc-popover-val">{account().name || 'MT5 Trader'}</span>
                </div>
                <div class="acc-popover-item">
                  <span class="acc-popover-label">Server / Broker</span>
                  <span class="acc-popover-val font-mono">{account().server || 'MetaQuotes'}</span>
                </div>
                <div class="acc-popover-item">
                  <span class="acc-popover-label">Account Type</span>
                  <span class="acc-popover-val">{account().account_type || 'Hedge'}</span>
                </div>
                <div class="acc-popover-item">
                  <span class="acc-popover-label">Base Currency</span>
                  <span class="acc-popover-val font-mono">{account().currency || 'USD'}</span>
                </div>
                <div class="acc-popover-item">
                  <span class="acc-popover-label">Leverage</span>
                  <span class="acc-popover-val font-mono text-accent">1:{account().leverage || 2000}</span>
                </div>
              </div>
            </div>
          </Show>
        </div>

        {/* Interactive Configuration Capsule Pills */}
        <div class="header-capsules-group">
          <button
            class="header-capsule-pill"
            onClick={props.onOpenRiskModal}
            title="Click to configure Working Capital, Risk Model, SL Presets, and R:R Ratio"
          >
            <span class="capsule-icon">⚙️</span>
            <span class="capsule-text">{riskSummaryText()}</span>
            <span class="capsule-arrow">▾</span>
          </button>

          <button
            class="header-capsule-pill"
            style={{
              'border-left-color': sampleInfo()?.badge_color || 'var(--accent-blue)',
            }}
            onClick={props.onOpenStrategyModal}
            title={`Sample Tier: ${sampleInfo()?.tier || 'Informational'} (${sampleInfo()?.total_trades || 0} trades). Click to view Strategy Sample Profile, Ralph Vince Optimal f, and Kelly math`}
          >
            <span class="capsule-icon">📊</span>
            <span class="capsule-text">{strategySummaryText()}</span>
            <span class="capsule-arrow">▾</span>
          </button>
        </div>
      </div>

      {/* Right Zone: System Toggles & Connection Status */}
      <div class="header-right-zone">
        <button
          class="btn-toggle"
          classList={{ active: preferencesStore.turboMode() }}
          onClick={handleTurboToggle}
          title="Toggle 500ms Turbo streaming rate"
        >
          <span class="toggle-indicator"></span>
          <span>{preferencesStore.turboMode() ? '⚡ Turbo (500ms)' : '🐢 Std (2s)'}</span>
        </button>

        <button
          class="btn-toggle"
          classList={{ active: preferencesStore.oneClickEnabled() }}
          onClick={handleOneClickToggle}
          title="Toggle instant One-Click order execution"
        >
          <span class="toggle-indicator"></span>
          <span>{preferencesStore.oneClickEnabled() ? '⚡ 1-Click: ON' : '🛡️ 1-Click: OFF'}</span>
        </button>

        <div
          class="connection-badge"
          classList={{ connected: isConnected() }}
          title={isConnected() ? 'Connected to MT5 Live Feed' : 'Connecting to MT5 Live Feed...'}
        >
          <span class="status-dot"></span>
          <span>{isConnected() ? 'MT5 LIVE' : 'OFFLINE'}</span>
        </div>
      </div>
    </header>
  );
};
