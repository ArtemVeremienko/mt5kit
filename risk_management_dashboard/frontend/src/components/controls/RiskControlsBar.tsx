import { Component, Show, createMemo } from 'solid-js';
import { preferencesStore } from '../../stores/preferencesStore';
import { accountStore } from '../../stores/accountStore';
import { marketStore } from '../../stores/marketStore';

export const RiskControlsBar: Component = () => {
  const tradeStats = marketStore.tradeStats;

  const activeRiskPctLabel = createMemo(() => {
    const method = preferencesStore.riskMethod();
    const customPct = preferencesStore.customRiskPct();
    const minFloor = preferencesStore.minRiskFloorPct();
    const maxCeiling = preferencesStore.maxRiskCeilingPct();
    const stats = tradeStats();

    if (method === 'fractional') return `${customPct.toFixed(1)}%`;
    if (method === 'kelly_half') {
      const rawPct = (stats.kelly_half ?? 0) * 100.0;
      if (rawPct < minFloor) return `${minFloor.toFixed(2)}% (🛡️ Floor)`;
      if (rawPct > maxCeiling) return `${maxCeiling.toFixed(2)}% (🔒 Capped)`;
      return `${rawPct.toFixed(2)}%`;
    }
    return '1.0%';
  });

  return (
    <div class="risk-controls-panel">
      <div class="control-group">
        <label class="control-label" for="working-capital">
          <span>WORKING CAPITAL ($)</span>
          <button
            class="btn-text-action"
            onClick={() => preferencesStore.resetWorkingCapital()}
            title="Reset Working Capital to deposited MT5 balance"
          >
            {preferencesStore.isWorkingCapitalCustom()
              ? `↺ Sync Balance ($${accountStore.account().balance?.toFixed(2) || '0.00'})`
              : `✓ MT5 Balance ($${accountStore.account().balance?.toFixed(2) || '0.00'})`}
          </button>
        </label>
        <div class="input-with-symbol">
          <span class="currency-prefix">$</span>
          <input
            id="working-capital"
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
      </div>

      <div class="control-group">
        <label class="control-label" for="risk-model">
          <span>RISK SIZING MODEL</span>
          <span class="badge-active-risk">{activeRiskPctLabel()}</span>
        </label>
        <select
          id="risk-model"
          class="control-select"
          value={preferencesStore.riskMethod()}
          onChange={(e) => preferencesStore.setRiskMethod(e.currentTarget.value)}
        >
          <option value="fractional">Fixed Fractional (% of Capital)</option>
          <option value="kelly_half">Dynamic Half-Kelly (f*/2)</option>
        </select>
      </div>

      <Show when={preferencesStore.riskMethod() === 'fractional'}>
        <div class="control-group">
          <label class="control-label" for="custom-risk-pct">
            <span>FRACTIONAL RISK (%)</span>
            <span class="control-value-tag">{preferencesStore.customRiskPct().toFixed(1)}%</span>
          </label>
          <input
            id="custom-risk-pct"
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

      <div class="control-group">
        <label class="control-label" for="sl-mode">
          <span>GLOBAL SL PRESET</span>
        </label>
        <select
          id="sl-mode"
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
      </div>

      <div class="control-group">
        <label class="control-label" for="rr-ratio">
          <span>R:R RATIO (TAKE PROFIT)</span>
        </label>
        <div class="input-with-symbol">
          <span class="currency-prefix">1:</span>
          <input
            id="rr-ratio"
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
      </div>
    </div>
  );
};
