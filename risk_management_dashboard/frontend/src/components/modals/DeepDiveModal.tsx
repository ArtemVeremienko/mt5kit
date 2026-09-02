import { Component, Show } from 'solid-js';
import { CalculatedSymbolResult } from '../../types';

interface Props {
  item: CalculatedSymbolResult | null;
  onClose: () => void;
}

export const DeepDiveModal: Component<Props> = (props) => {
  return (
    <Show when={props.item}>
      {(item) => (
        <div class="modal-backdrop" onClick={props.onClose}>
          <div class="modal-card modal-lg" onClick={(e) => e.stopPropagation()}>
            <div class="modal-header">
              <div class="modal-title-group">
                <span class="modal-icon">🔍</span>
                <h3 class="modal-title">
                  {item().spec.symbol} — Risk Math & Multi-Model Breakdown
                </h3>
              </div>
              <button class="modal-close-btn" onClick={props.onClose}>
                ✕
              </button>
            </div>

            <div class="modal-body">
              <div class="deep-dive-grid">
                <div class="deep-dive-card">
                  <div class="card-subtitle">BROKER SPECIFICATIONS</div>
                  <div class="spec-row">
                    <span class="spec-label">Contract Size:</span>
                    <span class="spec-val">{item().spec.trade_contract_size?.toLocaleString()}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Pip Size / Digits:</span>
                    <span class="spec-val">{item().spec.pip_size} ({item().spec.digits}d)</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Pip Value per Lot:</span>
                    <span class="spec-val">${item().calc.pip_val_display}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Min / Max Volume:</span>
                    <span class="spec-val">{item().calc.min_volume} / {item().calc.max_volume}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Volume Step:</span>
                    <span class="spec-val">{item().calc.volume_step}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">14D ADR / ATR:</span>
                    <span class="spec-val">{item().spec.adr_display} p / {item().spec.atr_display} p</span>
                  </div>
                </div>

                <div class="deep-dive-card">
                  <div class="card-subtitle">ACTIVE POSITION SIZING FORMULA</div>
                  <div class="spec-row">
                    <span class="spec-label">Working Capital:</span>
                    <span class="spec-val">${item().calc.working_capital.toFixed(2)}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Selected Risk Model:</span>
                    <span class="spec-val text-accent">{item().calc.risk_method}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Target Risk (% / $):</span>
                    <span class="spec-val">{item().calc.target_risk_pct.toFixed(2)}% (${item().calc.target_risk_amount.toFixed(2)})</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Stop Loss:</span>
                    <span class="spec-val">{item().calc.sl_pips} Pips</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Theoretical Exact Lot:</span>
                    <span class="spec-val font-mono">{item().calc.exact_lot_display}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Broker Executable Lot:</span>
                    <strong class="spec-val text-accent font-mono">{item().calc.lot_display}</strong>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Effective Risk (% / $):</span>
                    <span class="spec-val">{item().calc.risk_display}</span>
                  </div>
                  <div class="spec-row">
                    <span class="spec-label">Required Margin:</span>
                    <span class="spec-val">${item().calc.required_margin_display} ({item().calc.margin_utilization_display}%)</span>
                  </div>
                </div>
              </div>

              <div class="multi-model-comparison-table-wrapper">
                <div class="card-subtitle">MULTI-MODEL POSITION SIZING COMPARISON</div>
                <table class="comparison-table">
                  <thead>
                    <tr>
                      <th>Sizing Strategy</th>
                      <th>Target Risk</th>
                      <th>Executable Lot</th>
                      <th>Dollar Risk</th>
                      <th>Required Margin</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>Fixed Fractional (1.0%)</strong></td>
                      <td>1.0%</td>
                      <td>{item().comparison.fractional_1pct.lot} Lot</td>
                      <td>${item().comparison.fractional_1pct.risk_amount.toFixed(2)}</td>
                      <td>${item().comparison.fractional_1pct.margin.toFixed(2)}</td>
                    </tr>
                    <tr>
                      <td><strong>Dynamic Half-Kelly (Bounded)</strong></td>
                      <td>{item().comparison.half_kelly.risk_pct.toFixed(2)}%</td>
                      <td>{item().comparison.half_kelly.lot} Lot</td>
                      <td>${item().comparison.half_kelly.risk_amount.toFixed(2)}</td>
                      <td>${item().comparison.half_kelly.margin.toFixed(2)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="modal-footer">
              <button class="btn-primary" onClick={props.onClose}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </Show>
  );
};
