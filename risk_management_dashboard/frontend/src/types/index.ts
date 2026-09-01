export interface AccountSummary {
  balance: number;
  equity: number;
  margin: number;
  free_margin?: number;
  margin_free?: number;
  margin_level: number;
  leverage: number;
  profit?: number;
  currency: string;
  server: string;
  name: string;
  login: number;
  account_type?: string;
  is_live?: boolean;
}

export interface StepRule {
  pip_size: number;
  digits: number;
  normal_step: number;
  fast_step: number;
  precision_step: number;
  unit_label: string;
  stops_level_pips?: number;
}

export interface SymbolSpec {
  symbol: string;
  category: string;
  bid: number;
  ask: number;
  digits: number;
  point: number;
  pip_size: number;
  trade_contract_size: number;
  trade_tick_value: number;
  trade_tick_size: number;
  volume_min: number;
  volume_max: number;
  volume_step: number;
  pip_value_per_lot: number;
  spread_pips: number;
  adr_14_pips: number;
  atr_14_pips: number;
  currency_base?: string;
  currency_profit?: string;
  currency_margin?: string;
  bid_display?: string;
  ask_display?: string;
  spread_display?: string;
  adr_display?: string;
  atr_display?: string;
  step_rule?: StepRule;
  margin_per_lot?: number;
  margin_rate?: number;
}

export interface ModelComparison {
  lot: number;
  risk_pct: number;
  risk_amount: number;
  margin: number;
}

export interface LotCalculation {
  symbol: string;
  working_capital: number;
  deposited_cash: number;
  leverage: number;
  risk_method: string;
  target_risk_pct: number;
  target_risk_amount: number;
  sl_pips: number;
  pip_value_per_lot: number;
  pip_val_display: string;
  exact_lot: number;
  exact_lot_display: string;
  executable_lot: number;
  executable_lot_display: string;
  effective_risk_amount: number;
  effective_risk_pct: number;
  clamped_by_min: boolean;
  clamped_by_max: boolean;
  clamped_by_step: boolean;
  required_margin: number;
  required_margin_display: string;
  margin_utilization_pct: number;
  margin_utilization_display: string;
  is_margin_exceeded: boolean;
  margin_status: 'healthy' | 'warning' | 'exceeded';
}

export interface CalculatedSymbolResult {
  spec: SymbolSpec;
  calc: LotCalculation;
  comparison: {
    fractional_1pct: ModelComparison;
    half_kelly: ModelComparison;
    half_optimal_f: ModelComparison;
  };
}

export interface OpenPosition {
  ticket: number;
  symbol: string;
  type: 'BUY' | 'SELL';
  volume: number;
  price_open: number;
  price_current: number;
  sl: number;
  tp: number;
  profit: number;
  swap: number;
  pnl_pips: number;
  r_multiple: number | null;
  comment: string;
  magic: number;
  time: number;
  digits: number;
  pip_size: number;
  step_rule?: StepRule;
}

export interface SampleSizeInfo {
  tier: 'informational' | 'exploratory' | 'moderate' | 'robust';
  count: number;
  label: string;
  badge_color: string;
  message: string;
  recommendation: string;
}

export interface TradeStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  breakeven_trades: number;
  win_rate: number;
  loss_rate: number;
  avg_win: number;
  avg_loss: number;
  payoff_ratio: number;
  profit_factor: number;
  worst_loss: number;
  best_win: number;
  net_profit: number;
  kelly_full: number;
  kelly_half: number;
  kelly_quarter: number;
  optimal_f: number;
  optimal_f_half: number;
  optimal_f_quarter: number;
  sample_info?: SampleSizeInfo;
}

export interface ToastMessage {
  id: number;
  title: string;
  message: string;
  type: 'success' | 'warning' | 'error' | 'info';
}
