import { Component, Show, createMemo } from 'solid-js';
import { preferencesStore } from '../../stores/preferencesStore';
import { accountStore } from '../../stores/accountStore';
import { marketStore } from '../../stores/marketStore';
import { formatRrRatio } from '../../utils/formatters';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const RiskConfigModal: Component<Props> = (props) => {
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
      if (rawPct < minFloor) return `${minFloor.toFixed(2)}% (Floor)`;
      if (rawPct > maxCeiling) return `${maxCeiling.toFixed(2)}% (Capped)`;
      return `${rawPct.toFixed(2)}%`;
    }
    return '1.0%';
  });

  return (
    <Show when={props.isOpen}>
      <div class="modal-backdrop" onClick={() => props.onClose()}>
        <div class="modal-card" onClick={(e) => e.stopPropagation()}>
          <div class="modal-header">
            <div class="modal-title-group">
              <span class="modal-icon">⚙️</span>
              <h3 class="modal-title">Risk & Position Sizing Configuration</h3>
            </div>
            <button class="modal-close-btn" onClick={() => props.onClose()}>
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
                <option value="fractional">Fixed Fractional (% of Capital)</option>
                <option value="kelly_half">Dynamic Half-Kelly (f*/2) — Edge Proportional</option>
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

            {/* Quantitative Risk Boundaries (Only shown when Dynamic Half-Kelly is selected) */}
            <Show when={preferencesStore.riskMethod() === 'kelly_half'}>
              <div class="modal-section-divider" />
              <div class="form-group">
                <label class="form-label">
                  QUANTITATIVE RISK BOUNDARIES:
                </label>
                <div style={{ display: 'grid', 'grid-template-columns': '1fr 1fr', gap: '12px', 'margin-top': '6px' }}>
                  <div>
                    <label class="control-label" for="modal-min-floor" style={{ 'font-size': '11px', 'margin-bottom': '4px' }}>
                      MIN RISK FLOOR (%)
                    </label>
                    <div class="input-with-symbol">
                      <input
                        id="modal-min-floor"
                        type="number"
                        class="control-input"
                        step="0.05"
                        min="0.05"
                        max="1.0"
                        value={preferencesStore.minRiskFloorPct()}
                        onInput={(e) => {
                          const val = parseFloat(e.currentTarget.value);
                          if (!isNaN(val) && val > 0) preferencesStore.setMinRiskFloorPct(val);
                        }}
                      />
                      <span class="currency-suffix">%</span>
                    </div>
                  </div>
                  <div>
                    <label class="control-label" for="modal-max-ceiling" style={{ 'font-size': '11px', 'margin-bottom': '4px' }}>
                      MAX RISK CEILING (%)
                    </label>
                    <div class="input-with-symbol">
                      <input
                        id="modal-max-ceiling"
                        type="number"
                        class="control-input"
                        step="0.1"
                        min="1.0"
                        max="5.0"
                        value={preferencesStore.maxRiskCeilingPct()}
                        onInput={(e) => {
                          const val = parseFloat(e.currentTarget.value);
                          if (!isNaN(val) && val > 0) preferencesStore.setMaxRiskCeilingPct(val);
                        }}
                      />
                      <span class="currency-suffix">%</span>
                    </div>
                  </div>
                </div>
                <span class="form-help-text">
                  Enforces dynamic clamping on Half-Kelly during losing streaks (floor) or excessive sample edge (ceiling).
                </span>
              </div>
            </Show>

            <div class="modal-section-divider" />

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
              <div class="control-label-row">
                <label class="form-label" for="modal-rr-slider">
                  TAKE PROFIT (RISK:REWARD RATIO):
                </label>
                <span
                  class="control-value-tag font-mono"
                  classList={{ 'tag-off': preferencesStore.rrRatio() === 0 }}
                >
                  {formatRrRatio(preferencesStore.rrRatio(), { showUnit: true, offLabel: '🛡️ TP Off' })}
                </span>
              </div>
              <input
                id="modal-rr-slider"
                type="range"
                class="control-slider"
                min="0"
                max="5.0"
                step="0.1"
                value={preferencesStore.rrRatio()}
                onInput={(e) => preferencesStore.setRrRatio(parseFloat(e.currentTarget.value))}
              />
              <div class="preset-chips-row">
                <button
                  type="button"
                  class="chip-snap-btn chip-snap-off"
                  classList={{ active: preferencesStore.rrRatio() === 0 }}
                  onClick={() => preferencesStore.setRrRatio(0)}
                  title="Disable Take Profit (Manual Trailing Exit)"
                >
                  🛡️ Off
                </button>
                <button
                  type="button"
                  class="chip-snap-btn"
                  classList={{ active: Math.abs(preferencesStore.rrRatio() - 1.0) < 0.01 }}
                  onClick={() => preferencesStore.setRrRatio(1.0)}
                >
                  1:1
                </button>
                <button
                  type="button"
                  class="chip-snap-btn"
                  classList={{ active: Math.abs(preferencesStore.rrRatio() - 1.5) < 0.01 }}
                  onClick={() => preferencesStore.setRrRatio(1.5)}
                >
                  1:1.5
                </button>
                <button
                  type="button"
                  class="chip-snap-btn"
                  classList={{ active: Math.abs(preferencesStore.rrRatio() - 2.0) < 0.01 }}
                  onClick={() => preferencesStore.setRrRatio(2.0)}
                >
                  1:2
                </button>
                <button
                  type="button"
                  class="chip-snap-btn"
                  classList={{ active: Math.abs(preferencesStore.rrRatio() - 2.5) < 0.01 }}
                  onClick={() => preferencesStore.setRrRatio(2.5)}
                >
                  1:2.5
                </button>
                <button
                  type="button"
                  class="chip-snap-btn"
                  classList={{ active: Math.abs(preferencesStore.rrRatio() - 3.0) < 0.01 }}
                  onClick={() => preferencesStore.setRrRatio(3.0)}
                >
                  1:3
                </button>
                <button
                  type="button"
                  class="chip-snap-btn"
                  classList={{ active: Math.abs(preferencesStore.rrRatio() - 4.0) < 0.01 }}
                  onClick={() => preferencesStore.setRrRatio(4.0)}
                >
                  1:4
                </button>
              </div>
              <span class="form-help-text">
                Multiplier applied to Stop Loss pips (e.g. 1:1.5 creates a 30 pip TP for a 20 pip SL). Select Off for manual runner.
              </span>
            </div>

            <div class="modal-section-divider" />

            {/* SL/TP Popover Editor Preferences */}
            <div class="form-group">
              <label class="form-label" for="modal-sltp-focus">
                SL/TP EDITOR DEFAULT FOCUS FIELD:
              </label>
              <select
                id="modal-sltp-focus"
                class="control-select"
                value={preferencesStore.defaultSltpFocusField()}
                onInput={(e) =>
                  preferencesStore.setDefaultSltpFocusField(
                    e.currentTarget.value as 'price' | 'pips' | 'cash'
                  )
                }
                onChange={(e) =>
                  preferencesStore.setDefaultSltpFocusField(
                    e.currentTarget.value as 'price' | 'pips' | 'cash'
                  )
                }
              >
                <option value="price">Price Level (e.g. 1.15945)</option>
                <option value="pips">Pip Distance (e.g. 25.0 pips)</option>
                <option value="cash">Profit / Loss $ (e.g. -$50.00)</option>
              </select>
              <span class="form-help-text">
                Field automatically focused and selected when opening the in-place SL/TP editor.
              </span>
            </div>

            <div class="modal-section-divider" />

            {/* 1-Click Order Execution Setting */}
            <div class="form-group">
              <div class="control-label-row">
                <label class="form-label">
                  1-CLICK INSTANT EXECUTION:
                </label>
                <button
                  type="button"
                  class="btn-toggle-compact"
                  classList={{ active: preferencesStore.oneClickEnabled() }}
                  onClick={() => preferencesStore.toggleOneClick()}
                  title="Toggle 1-Click Instant Execution"
                >
                  <span class="toggle-indicator"></span>
                  <span class="toggle-text">
                    {preferencesStore.oneClickEnabled() ? '⚡ Active (Instant)' : '🛡️ Confirmation Modal'}
                  </span>
                </button>
              </div>
              <span class="form-help-text">
                When enabled, clicking BUY or SELL dispatches market orders instantly without displaying the confirmation modal.
              </span>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-primary" onClick={() => props.onClose()}>
              Done
            </button>
          </div>
        </div>
      </div>
    </Show>
  );
};
