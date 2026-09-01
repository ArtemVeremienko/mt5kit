import { Component, Show, createMemo } from 'solid-js';
import { preferencesStore } from '../../stores/preferencesStore';
import { accountStore } from '../../stores/accountStore';
import { marketStore } from '../../stores/marketStore';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const RiskConfigModal: Component<Props> = (props) => {
  const tradeStats = marketStore.tradeStats;

  const activeRiskPctLabel = createMemo(() => {
    const method = preferencesStore.riskMethod();
    const customPct = preferencesStore.customRiskPct();
    const stats = tradeStats();

    if (method === 'fractional') return `${customPct.toFixed(1)}%`;
    if (method === 'kelly_full') return `${((stats.kelly_full ?? 0) * 100).toFixed(1)}%`;
    if (method === 'kelly_half') return `${((stats.kelly_half ?? 0) * 100).toFixed(1)}%`;
    if (method === 'kelly_quarter') return `${((stats.kelly_quarter ?? 0) * 100).toFixed(1)}%`;
    if (method === 'optimal_f_full') return `${((stats.optimal_f ?? 0) * 100).toFixed(1)}%`;
    if (method === 'optimal_f_half') return `${((stats.optimal_f_half ?? 0) * 100).toFixed(1)}%`;
    if (method === 'optimal_f_quarter') return `${((stats.optimal_f_quarter ?? 0) * 100).toFixed(1)}%`;
    return '1.0%';
  });

  return (
    <Show when={props.isOpen}>
      <div class="modal-backdrop" onClick={props.onClose}>
        <div class="modal-card" onClick={(e) => e.stopPropagation()}>
          <div class="modal-header">
            <div class="modal-title-group">
              <span class="modal-icon">⚙️</span>
              <h3 class="modal-title">Risk & Position Sizing Configuration</h3>
            </div>
            <button class="modal-close-btn" onClick={props.onClose}>
              ✕
            </button>
          </div>

          <div class="modal-body">
            {/* Working Capital */}
            <div class="form-group">
              <div class="control-label-row">
                <label class="form-label" for="modal-working-capital">
                  WORKING CAPITAL ($):
                </label>
                <button
                  class="btn-text-action"
                  onClick={() => preferencesStore.resetWorkingCapital()}
                  title="Reset Working Capital to live MT5 balance"
                >
                  {preferencesStore.isWorkingCapitalCustom()
                    ? `↺ Sync Balance ($${accountStore.account().balance?.toFixed(2) || '0.00'})`
                    : `✓ Synced with MT5 ($${accountStore.account().balance?.toFixed(2) || '0.00'})`}
                </button>
              </div>
              <div class="input-with-symbol">
                <span class="currency-prefix">$</span>
                <input
                  id="modal-working-capital"
                  type="number"
                  class="control-input"
                  step="10"
                  min="1"
                  value={preferencesStore.workingCapital()}
                  onInput={(e) => {
                    const val = parseFloat(e.currentTarget.value);
                    if (!isNaN(val) && val > 0) preferencesStore.setWorkingCapital(val);
                  }}
                />
              </div>
              <span class="form-help-text">
                Base capital used for position sizing (independent of deposited margin cash).
              </span>
            </div>

            {/* Risk Sizing Model */}
            <div class="form-group">
              <div class="control-label-row">
                <label class="form-label" for="modal-risk-model">
                  POSITION SIZING MODEL:
                </label>
                <span class="badge-active-risk">{activeRiskPctLabel()} Target Risk</span>
              </div>
              <select
                id="modal-risk-model"
                class="control-select"
                value={preferencesStore.riskMethod()}
                onChange={(e) => preferencesStore.setRiskMethod(e.currentTarget.value)}
              >
                <optgroup label="Fixed Risk Models">
                  <option value="fractional">Fixed Fractional (% of Capital)</option>
                </optgroup>
                <optgroup label="Kelly Criterion Models (Win Rate & Payoff)">
                  <option value="kelly_half">Half Kelly (Recommended for Forex)</option>
                  <option value="kelly_quarter">Quarter Kelly (Conservative)</option>
                  <option value="kelly_full">Full Kelly (Aggressive Theoretical Max)</option>
                </optgroup>
                <optgroup label="Ralph Vince Optimal f Models (TWR Optimization)">
                  <option value="optimal_f_half">Half Optimal f (Balanced Growth)</option>
                  <option value="optimal_f_quarter">Quarter Optimal f (Conservative)</option>
                  <option value="optimal_f_full">Full Optimal f (Aggressive TWR Peak)</option>
                </optgroup>
              </select>
            </div>

            {/* Custom Fractional Slider */}
            <Show when={preferencesStore.riskMethod() === 'fractional'}>
              <div class="form-group">
                <div class="control-label-row">
                  <label class="form-label" for="modal-fractional-risk">
                    FRACTIONAL RISK PERCENTAGE:
                  </label>
                  <span class="control-value-tag">{preferencesStore.customRiskPct().toFixed(1)}%</span>
                </div>
                <input
                  id="modal-fractional-risk"
                  type="range"
                  class="control-slider"
                  min="0.1"
                  max="10.0"
                  step="0.1"
                  value={preferencesStore.customRiskPct()}
                  onInput={(e) => preferencesStore.setCustomRiskPct(parseFloat(e.currentTarget.value))}
                />
              </div>
            </Show>

            {/* Global Stop Loss Preset */}
            <div class="form-group">
              <label class="form-label" for="modal-sl-mode">
                GLOBAL STOP LOSS PRESET:
              </label>
              <select
                id="modal-sl-mode"
                class="control-select"
                value={preferencesStore.slMode()}
                onChange={(e) => preferencesStore.setSlMode(e.currentTarget.value)}
              >
                <option value="1/4 ADR">1/4 ADR (Scalping / Intraday)</option>
                <option value="1/3 ADR">1/3 ADR (Day Trading Preset)</option>
                <option value="1/2 ADR">1/2 ADR (Standard Swing)</option>
                <option value="1 ADR">1.0 ADR (Full Daily Range)</option>
                <option value="1 ATR">1.0 ATR (14D Volatility)</option>
              </select>
              <span class="form-help-text">
                Dynamic SL auto-calculated from 14-day average daily volatility in pips.
              </span>
            </div>

            {/* Take Profit Risk:Reward Ratio */}
            <div class="form-group">
              <label class="form-label" for="modal-rr-ratio">
                TAKE PROFIT (RISK:REWARD RATIO):
              </label>
              <div class="input-with-symbol">
                <span class="currency-prefix">1:</span>
                <input
                  id="modal-rr-ratio"
                  type="number"
                  class="control-input"
                  step="0.1"
                  min="0"
                  max="10"
                  value={preferencesStore.rrRatio()}
                  onInput={(e) => {
                    const val = parseFloat(e.currentTarget.value);
                    if (!isNaN(val) && val >= 0) preferencesStore.setRrRatio(val);
                  }}
                />
              </div>
              <span class="form-help-text">
                Multiplier applied to Stop Loss pips (e.g. 1:1.5 creates a 30 pip TP for a 20 pip SL). Set 0 for no TP.
              </span>
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
