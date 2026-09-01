import { Component, Show } from 'solid-js';
import { marketStore } from '../../stores/marketStore';
import { preferencesStore } from '../../stores/preferencesStore';

interface Props {
  onOpenManualModal: () => void;
  onOpenCsvModal: () => void;
}

export const StrategyStatsBanner: Component<Props> = (props) => {
  const tradeStats = marketStore.tradeStats;
  const sampleInfo = marketStore.sampleInfo;

  return (
    <div class="strategy-stats-section">
      <div class="stats-accordion-bar" onClick={preferencesStore.toggleStatsBanner}>
        <div class="stats-accordion-left">
          <span class="stats-icon">📊</span>
          <span class="stats-summary-title">Strategy Sample Profile</span>
          <span class="stats-divider">•</span>
          <span class="stats-summary-highlight">
            {tradeStats().total_trades || 120} Trades
          </span>
          <span class="stats-divider">•</span>
          <span class="stats-summary-highlight">
            {((tradeStats().win_rate || 0.55) * 100).toFixed(0)}% Win Rate
          </span>
          <span class="stats-divider">•</span>
          <span class="stats-summary-highlight">
            {(tradeStats().payoff_ratio || 1.5).toFixed(2)} R/R
          </span>
          <span class="stats-divider">•</span>
          <span class="stats-summary-highlight">
            Profit Factor: {(tradeStats().profit_factor || 1.83).toFixed(2)}
          </span>
          <Show when={sampleInfo()}>
            {(info) => (
              <span
                class="badge-tier"
                style={{ 'background-color': `${info().badge_color}22`, color: info().badge_color, 'border-color': `${info().badge_color}55` }}
              >
                {info().label}
              </span>
            )}
          </Show>
        </div>

        <div class="stats-accordion-right">
          <button
            class="btn-sm btn-ghost"
            onClick={(e) => {
              e.stopPropagation();
              props.onOpenManualModal();
            }}
            title="Configure manual strategy win rate, payoff ratio, and worst loss"
          >
            ⚙️ Strategy Params
          </button>
          <button
            class="btn-sm btn-ghost"
            onClick={(e) => {
              e.stopPropagation();
              props.onOpenCsvModal();
            }}
            title="Upload CSV closed trades history"
          >
            📁 Import CSV
          </button>
          <span class="accordion-toggle-icon">
            {preferencesStore.showStatsBanner() ? '▲ Collapse' : '▼ Expand'}
          </span>
        </div>
      </div>

      <Show when={preferencesStore.showStatsBanner()}>
        <div class="stats-details-drawer">
          <div class="stat-drawer-grid">
            <div class="stat-mini-card">
              <div class="stat-mini-label">TOTAL SAMPLE</div>
              <div class="stat-mini-val">{tradeStats().total_trades ?? 0} Trades</div>
              <div class="stat-mini-sub">
                {tradeStats().winning_trades ?? 0} Wins / {tradeStats().losing_trades ?? 0} Losses
              </div>
            </div>

            <div class="stat-mini-card">
              <div class="stat-mini-label">WIN RATE / PAYOFF</div>
              <div class="stat-mini-val">
                {((tradeStats().win_rate ?? 0.55) * 100).toFixed(1)}% / {(tradeStats().payoff_ratio ?? 0).toFixed(2)}b
              </div>
              <div class="stat-mini-sub">
                Avg Win: ${tradeStats().avg_win?.toFixed(2) ?? '0.00'} | Avg Loss: ${tradeStats().avg_loss?.toFixed(2) ?? '0.00'}
              </div>
            </div>

            <div class="stat-mini-card">
              <div class="stat-mini-label">KELLY CRITERION (f*)</div>
              <div class="stat-mini-val text-accent">
                {((tradeStats().kelly_full ?? 0) * 100).toFixed(1)}%
              </div>
              <div class="stat-mini-sub">
                Half: {((tradeStats().kelly_half ?? 0) * 100).toFixed(1)}% | Qtr: {((tradeStats().kelly_quarter ?? 0) * 100).toFixed(1)}%
              </div>
            </div>

            <div class="stat-mini-card">
              <div class="stat-mini-label">OPTIMAL f (RALPH VINCE)</div>
              <div class="stat-mini-val text-accent">
                {((tradeStats().optimal_f ?? 0) * 100).toFixed(1)}%
              </div>
              <div class="stat-mini-sub">
                Worst Loss: ${tradeStats().worst_loss?.toFixed(2) ?? '0.00'} | Half: {((tradeStats().optimal_f_half ?? 0) * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          <Show when={sampleInfo()}>
            {(info) => (
              <div class="sample-tier-alert" style={{ 'border-left-color': info().badge_color }}>
                <div class="tier-alert-title" style={{ color: info().badge_color }}>
                  {info().message}
                </div>
                <div class="tier-alert-rec">{info().recommendation}</div>
              </div>
            )}
          </Show>
        </div>
      </Show>
    </div>
  );
};
