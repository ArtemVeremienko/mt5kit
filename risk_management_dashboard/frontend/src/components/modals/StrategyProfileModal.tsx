import { Component, Show } from 'solid-js';
import { marketStore } from '../../stores/marketStore';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onOpenManualModal: () => void;
  onOpenCsvModal: () => void;
}

export const StrategyProfileModal: Component<Props> = (props) => {
  const tradeStats = marketStore.tradeStats;
  const sampleInfo = marketStore.sampleInfo;

  return (
    <Show when={props.isOpen}>
      <div class="modal-backdrop" onClick={props.onClose}>
        <div class="modal-card modal-lg" onClick={(e) => e.stopPropagation()}>
          <div class="modal-header">
            <div class="modal-title-group">
              <span class="modal-icon">📊</span>
              <h3 class="modal-title">Strategy Sample Profile & Quantitative Performance</h3>
            </div>
            <button class="modal-close-btn" onClick={props.onClose}>
              ✕
            </button>
          </div>

          <div class="modal-body">
            {/* Sample Tier Alert Banner */}
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

            {/* 4-Card Analytics Grid */}
            <div class="stat-drawer-grid">
              <div class="stat-mini-card">
                <div class="stat-mini-label">WIN RATE & ACCURACY</div>
                <div class="stat-mini-val">
                  {((tradeStats().win_rate || 0.55) * 100).toFixed(1)}%
                </div>
                <div class="stat-mini-sub">
                  Sample Size: <strong>{tradeStats().total_trades || 120} Closed Trades</strong>
                </div>
              </div>

              <div class="stat-mini-card">
                <div class="stat-mini-label">PAYOFF & PROFIT FACTOR</div>
                <div class="stat-mini-val">
                  {(tradeStats().payoff_ratio || 1.5).toFixed(2)} R/R
                </div>
                <div class="stat-mini-sub">
                  Profit Factor: <strong>{(tradeStats().profit_factor || 1.83).toFixed(2)}</strong> | Avg Win/Loss: ${tradeStats().avg_win?.toFixed(2) || '60.00'}/${tradeStats().avg_loss?.toFixed(2) || '40.00'}
                </div>
              </div>

              <div class="stat-mini-card">
                <div class="stat-mini-label">KELLY CRITERION (f*)</div>
                <div class="stat-mini-val text-accent">
                  {((tradeStats().kelly_full || 0.25) * 100).toFixed(1)}%
                </div>
                <div class="stat-mini-sub">
                  Half: {((tradeStats().kelly_half || 0.125) * 100).toFixed(1)}% | Quarter: {((tradeStats().kelly_quarter || 0.0625) * 100).toFixed(1)}%
                </div>
              </div>

              <div class="stat-mini-card">
                <div class="stat-mini-label">OPTIMAL f (RALPH VINCE)</div>
                <div class="stat-mini-val text-accent">
                  {((tradeStats().optimal_f || 0.12) * 100).toFixed(1)}%
                </div>
                <div class="stat-mini-sub">
                  Worst Loss: ${tradeStats().worst_loss?.toFixed(2) || '100.00'} | Half: {((tradeStats().optimal_f_half || 0.06) * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Action Bar inside Modal */}
            <div class="strategy-modal-actions">
              <button
                class="btn-ghost"
                onClick={() => {
                  props.onClose();
                  props.onOpenManualModal();
                }}
                title="Override win rate, payoff ratio, or sample size manually"
              >
                ⚙️ Edit Strategy Parameters
              </button>
              <button
                class="btn-ghost"
                onClick={() => {
                  props.onClose();
                  props.onOpenCsvModal();
                }}
                title="Upload MT5/MT4 closed trade report CSV"
              >
                📁 Import Closed Trades CSV
              </button>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-primary" onClick={props.onClose}>
              Done
            </button>
          </div>
        </div>
      </div>
    </Show>
  );
};
