import { Component } from 'solid-js';
import { accountStore } from '../../stores/accountStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { positionsStore } from '../../stores/positionsStore';
import { toastStore } from '../../stores/toastStore';
import { wsService } from '../../services/websocket';
import { formatCurrency } from '../../utils/formatters';

export const HeaderMetricsBar: Component = () => {
  const account = accountStore.account;
  const isConnected = accountStore.isConnected;
  const floatingProfit = positionsStore.totalFloatingProfit;

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

  return (
    <header class="dashboard-header">
      <div class="header-brand">
        <div class="brand-logo">
          <span class="logo-icon">⚡</span>
          <div>
            <div class="brand-title">MT5 RISK ENGINE</div>
            <div class="brand-subtitle">SOLID.JS FINE-GRAINED REACTIVE MATRIX</div>
          </div>
        </div>
      </div>

      <div class="account-metrics-bar">
        <div class="metric-card">
          <div class="metric-label">DEPOSITED BALANCE</div>
          <div class="metric-value">{formatCurrency(account().balance)}</div>
        </div>

        <div class="metric-card">
          <div class="metric-label">EQUITY</div>
          <div class="metric-value">{formatCurrency(account().equity)}</div>
        </div>

        <div class="metric-card">
          <div class="metric-label">FLOATING P&L</div>
          <div
            class="metric-value"
            classList={{
              'text-profit': floatingProfit() > 0,
              'text-loss': floatingProfit() < 0,
            }}
          >
            {floatingProfit() >= 0 ? `+${formatCurrency(floatingProfit())}` : formatCurrency(floatingProfit())}
          </div>
        </div>

        <div class="metric-card">
          <div class="metric-label">LEVERAGE</div>
          <div class="metric-value">1:{account().leverage || 300}</div>
        </div>
      </div>

      <div class="header-actions">
        <button
          class="btn-toggle"
          classList={{ active: preferencesStore.turboMode() }}
          onClick={handleTurboToggle}
          title="Toggle 500ms Turbo streaming rate"
        >
          <span class="toggle-indicator"></span>
          <span>{preferencesStore.turboMode() ? '⚡ Turbo (500ms)' : '🐢 Standard (2s)'}</span>
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
