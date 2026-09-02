import { Component, Show, createMemo, createSignal, onCleanup } from 'solid-js';
import { preferencesStore } from '../../stores/preferencesStore';
import { accountStore } from '../../stores/accountStore';
import { marketStore } from '../../stores/marketStore';

export const RiskControlsBar: Component = () => {
  const tradeStats = marketStore.tradeStats;

  const [isEditingWc, setIsEditingWc] = createSignal(false);
  const [wcDraft, setWcDraft] = createSignal('');
  let debounceTimer: ReturnType<typeof setTimeout> | undefined;

  onCleanup(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
  });

  const handleWcInput = (rawVal: string) => {
    setWcDraft(rawVal);
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const val = parseFloat(rawVal);
      if (!isNaN(val) && val > 0) {
        preferencesStore.setWorkingCapital(val);
      }
    }, 600);
  };

  const commitWcImmediately = (rawVal: string) => {
    if (debounceTimer) clearTimeout(debounceTimer);
    const val = parseFloat(rawVal);
    if (!isNaN(val) && val > 0) {
      preferencesStore.setWorkingCapital(val);
    }
    setIsEditingWc(false);
  };

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

  const formatWcDisplay = (val: number) => {
    return val % 1 === 0 ? val.toString() : val.toFixed(2);
  };

  return (
    <div class="risk-controls-panel">
      <div class="control-group">
        <label class="control-label" for="working-capital">
          <div style={{ display: 'flex', 'align-items': 'center', gap: '6px' }}>
            <span>WORKING CAPITAL ($)</span>
            <Show when={preferencesStore.isWorkingCapitalCustom()}>
              <span
                class="control-value-tag font-mono"
                style={{
                  'font-size': '10px',
                  'background': 'rgba(245, 158, 11, 0.15)',
                  'color': '#fbbf24',
                  'border': '1px solid rgba(245, 158, 11, 0.3)',
                  'padding': '1px 5px',
                  'border-radius': '4px',
                }}
                title={`Delta (Δ): ${preferencesStore.reserveDelta()! >= 0 ? '+' : ''}$${preferencesStore.reserveDelta()?.toFixed(2)} relative to MT5 balance`}
              >
                Δ: {preferencesStore.reserveDelta()! >= 0 ? '+' : '-'}${Math.abs(preferencesStore.reserveDelta() || 0).toFixed(0)}
              </span>
            </Show>
          </div>
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
            value={isEditingWc() ? wcDraft() : formatWcDisplay(preferencesStore.workingCapital())}
            onFocus={() => {
              setIsEditingWc(true);
              setWcDraft(formatWcDisplay(preferencesStore.workingCapital()));
            }}
            onInput={(e) => handleWcInput(e.currentTarget.value)}
            onBlur={() => commitWcImmediately(wcDraft())}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                commitWcImmediately(wcDraft());
                e.currentTarget.blur();
              }
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
