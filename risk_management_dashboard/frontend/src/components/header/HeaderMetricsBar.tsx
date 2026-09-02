import { Component, Show, createMemo, createSignal, createEffect, onCleanup } from 'solid-js';
import { accountStore } from '../../stores/accountStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { positionsStore } from '../../stores/positionsStore';
import { marketStore } from '../../stores/marketStore';
import { toastStore } from '../../stores/toastStore';
import { wsService } from '../../services/websocket';
import { formatCurrency, formatRrRatio } from '../../utils/formatters';

interface Props {
  onOpenRiskModal: () => void;
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
  const [isStatsHovered, setIsStatsHovered] = createSignal<boolean>(false);
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

  // Structured Risk summary tags
  const riskModelTag = createMemo(() => {
    const method = preferencesStore.riskMethod();
    const customPct = preferencesStore.customRiskPct();
    const stats = tradeStats();

    if (method === 'fractional') {
      return `${customPct.toFixed(1)}% Fixed`;
    }
    if (method === 'kelly_half') {
      const raw = (stats.kelly_half ?? 0) * 100;
      const minF = preferencesStore.minRiskFloorPct();
      const maxC = preferencesStore.maxRiskCeilingPct();
      const bounded = Math.max(minF, Math.min(maxC, raw));
      const suffix = raw < minF ? ' (Floor)' : raw > maxC ? ' (Cap)' : '';
      return `${bounded.toFixed(2)}% ½-Kelly${suffix}`;
    }
    return '1.0% Fixed';
  });

  const slPresetTag = createMemo(() => preferencesStore.slMode());
  const rrRatioTag = createMemo(() => formatRrRatio(preferencesStore.rrRatio()));

  // Structured Strategy summary tags
  const tradesCountTag = createMemo(() => `${tradeStats().total_trades || 0} Trades`);
  const winRateTag = createMemo(() => `${((tradeStats().win_rate || 0) * 100).toFixed(0)}% WR`);
  const profitFactorTag = createMemo(() => `PF ${(tradeStats().profit_factor || 0).toFixed(2)}`);
  const halfKellyTag = createMemo(() => `½K ${((tradeStats().kelly_half || 0) * 100).toFixed(1)}%`);

  return (
    <header class="dashboard-header">
      {/* Left Zone: Brand Glyph & Workspace Switcher */}
      <div class="header-left-zone">
        <div class="brand-logo-compact" title="MetaTrader 5 Institutional Risk Engine">
          <span class="logo-icon-compact">⚡</span>
        </div>

        <div class="header-workspace-switcher">
          <button
            class="header-nav-btn"
            classList={{ active: activeView() === 'matrix' }}
            onClick={() => preferencesStore.setActiveView('matrix')}
            title="Market Risk & Execution Matrix (Hotkey: 1)"
          >
            <span class="btn-icon">🎯</span>
            <span class="btn-text">Matrix</span>
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
            <kbd class="btn-kbd">2</kbd>
          </button>
        </div>
      </div>

      {/* Center Zone: Account Telemetry + Horizontal Dual Pills */}
      <div class="header-center-zone">
        <div class="account-inline-metrics-container" ref={accountInfoRef}>
          <div class="account-inline-metrics">
            <div
              class="metric-mini-group clickable"
              classList={{ 'is-overridden': preferencesStore.isWorkingCapitalCustom() }}
              onClick={() => props.onOpenRiskModal()}
              title={
                preferencesStore.isWorkingCapitalCustom()
                  ? `Custom Working Capital: ${formatCurrency(preferencesStore.workingCapital())} (MT5 Balance: ${formatCurrency(account().balance || 0.0)}) · Click to configure or reset`
                  : `Deposited Balance in MT5 Account: ${formatCurrency(account().balance || 0.0)} · Click to customize Working Capital`
              }
            >
              <span class="metric-mini-label">
                {preferencesStore.isWorkingCapitalCustom() ? 'WC' : 'BAL'}
              </span>
              <span
                class="metric-mini-val font-mono"
                classList={{ 'wc-highlight': preferencesStore.isWorkingCapitalCustom() }}
              >
                {preferencesStore.isWorkingCapitalCustom()
                  ? formatCurrency(preferencesStore.workingCapital())
                  : formatCurrency(account().balance || 0.0)}
              </span>
              <Show when={preferencesStore.isWorkingCapitalCustom()}>
                <span class="wc-badge-dot" title="Custom Working Capital Active">●</span>
              </Show>
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

            <div class="metric-mini-group" title="Net Real-Time Equity">
              <span class="metric-mini-label">EQ</span>
              <span class="metric-mini-val font-mono">{formatCurrency(account().equity || 0.0)}</span>
            </div>

            <button
              type="button"
              class="btn-account-info"
              classList={{ active: isAccountInfoOpen() }}
              onClick={() => setIsAccountInfoOpen(!isAccountInfoOpen())}
              title="Click to view full MT5 Account Info (Leverage, Server, Login)"
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

        {/* Horizontal Dual Pills */}
        <div class="header-pills-row">
          {/* Pill 1: Risk Rule Configuration */}
          <button
            class="header-nav-pill risk-pill"
            onClick={() => props.onOpenRiskModal()}
            title={`Active Risk Rules: ${riskModelTag()} · ${slPresetTag()} · ${rrRatioTag()} (Click to configure)`}
          >
            <span class="pill-icon">🎯</span>
            <div class="pill-content">
              <span class="pill-chip chip-risk-model">{riskModelTag()}</span>
              <span class="pill-divider">|</span>
              <span class="pill-chip chip-sl-preset">{slPresetTag()}</span>
              <span class="pill-divider">|</span>
              <span class="pill-chip chip-rr-ratio">{rrRatioTag()}</span>
            </div>
            <span class="pill-arrow">⚙️</span>
          </button>

          {/* Pill 2: Strategy Performance Telemetry (Read-Only Indicative Display with HTML Popover) */}
          <div
            class="stats-pill-wrapper"
            onMouseEnter={() => setIsStatsHovered(true)}
            onMouseLeave={() => setIsStatsHovered(false)}
          >
            <div
              class="header-nav-pill stats-pill read-only"
              style={{
                '--tier-color': sampleInfo()?.badge_color || 'var(--accent-blue)',
              }}
            >
              <span class="pill-icon">📊</span>
              <div class="pill-content">
                <span class="pill-chip chip-deals">{tradesCountTag()}</span>
                <span class="pill-divider">|</span>
                <span
                  class="pill-chip chip-wr"
                  classList={{
                    'chip-wr-good': (tradeStats().win_rate || 0) >= 0.5,
                    'chip-wr-sub': (tradeStats().win_rate || 0) < 0.5,
                  }}
                >
                  {winRateTag()}
                </span>
                <span class="pill-divider">|</span>
                <span class="pill-chip chip-pf">{profitFactorTag()}</span>
                <span class="pill-divider">|</span>
                <span class="pill-chip chip-kelly">{halfKellyTag()}</span>
              </div>
            </div>

            {/* Rich HTML Telemetry Popover */}
            <Show when={isStatsHovered()}>
              <div class="stats-telemetry-popover">
                <div class="stats-popover-header">
                  <div class="stats-popover-title-group">
                    <span class="stats-popover-icon">📊</span>
                    <span class="stats-popover-title">STRATEGY PERFORMANCE TELEMETRY</span>
                  </div>
                  <span
                    class="stats-popover-badge"
                    style={{
                      color: sampleInfo()?.badge_color || '#60a5fa',
                      'border-color': `${sampleInfo()?.badge_color || '#60a5fa'}40`,
                      'background-color': `${sampleInfo()?.badge_color || '#60a5fa'}18`,
                    }}
                  >
                    {sampleInfo()?.label || 'Baseline'}
                  </span>
                </div>

                <div class="stats-popover-grid">
                  <div class="stats-popover-item">
                    <span class="stats-popover-label">Total Closed Trades</span>
                    <span class="stats-popover-val font-mono">{tradeStats().total_trades || 0}</span>
                  </div>
                  <div class="stats-popover-item">
                    <span class="stats-popover-label">Win Rate</span>
                    <span
                      class="stats-popover-val font-mono font-bold"
                      classList={{
                        'text-profit': (tradeStats().win_rate || 0) >= 0.5,
                        'text-loss': (tradeStats().win_rate || 0) < 0.5,
                      }}
                    >
                      {((tradeStats().win_rate || 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div class="stats-popover-item">
                    <span class="stats-popover-label">Profit Factor</span>
                    <span class="stats-popover-val font-mono">{(tradeStats().profit_factor || 0).toFixed(2)}</span>
                  </div>
                  <div class="stats-popover-item">
                    <span class="stats-popover-label">Payoff Ratio (R:R)</span>
                    <span class="stats-popover-val font-mono">{(tradeStats().payoff_ratio || 0).toFixed(2)}</span>
                  </div>
                  <div class="stats-popover-item">
                    <span class="stats-popover-label">Average Win / Loss</span>
                    <span class="stats-popover-val font-mono">
                      <span class="text-profit">+${(tradeStats().avg_win || 0).toFixed(2)}</span>
                      {' / '}
                      <span class="text-loss">-${Math.abs(tradeStats().avg_loss || 0).toFixed(2)}</span>
                    </span>
                  </div>
                  <div class="stats-popover-item">
                    <span class="stats-popover-label">Dynamic Half-Kelly</span>
                    <span class="stats-popover-val font-mono text-accent font-bold">
                      {((tradeStats().kelly_half || 0) * 100).toFixed(2)}%
                    </span>
                  </div>
                </div>

                <div class="stats-popover-footer">
                  <span class="stats-popover-note">
                    {(tradeStats().total_trades || 0) < 100
                      ? '⚠️ Sample < 100 trades: Sizing defaults to Fixed 1.0% until statistical confidence is reached.'
                      : '✅ Statistically robust sample tier for dynamic fractional sizing.'}
                  </span>
                </div>
              </div>
            </Show>
          </div>
        </div>
      </div>

      {/* Right Zone: Compact Toggles & Pulsing Connection Indicator */}
      <div class="header-right-zone">
        <button
          class="btn-toggle-compact"
          classList={{ active: preferencesStore.turboMode() }}
          onClick={handleTurboToggle}
          title={preferencesStore.turboMode() ? 'Turbo Mode (500ms streaming)' : 'Standard Mode (2.0s streaming)'}
        >
          <span class="toggle-indicator"></span>
          <span class="toggle-text">{preferencesStore.turboMode() ? '⚡ 500ms' : '🐢 2s'}</span>
        </button>

        <button
          class="btn-toggle-compact btn-header-settings"
          classList={{ 'has-one-click': preferencesStore.oneClickEnabled() }}
          onClick={() => props.onOpenRiskModal()}
          title={
            preferencesStore.oneClickEnabled()
              ? 'Terminal Settings (⚡ 1-Click Instant Execution Active)'
              : 'Terminal Settings & Risk Configuration'
          }
        >
          <span class="toggle-text">
            {preferencesStore.oneClickEnabled() ? '⚡ Settings' : '⚙️ Settings'}
          </span>
        </button>

        {/* Pulsing Status Beacon */}
        <div
          class="connection-dot-beacon"
          classList={{ connected: isConnected() }}
          title={isConnected() ? `Connected: ${account().server || 'MT5 Live Feed'}` : 'Disconnected from MT5'}
        >
          <span class="beacon-pulse"></span>
          <span class="beacon-core"></span>
        </div>
      </div>
    </header>
  );
};
