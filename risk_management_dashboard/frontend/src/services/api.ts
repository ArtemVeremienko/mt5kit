import { AccountSummary, OpenPosition, TradeStats, SampleSizeInfo, SymbolSpec } from '../types';

export interface ExecuteOrderPayload {
  symbol: string;
  action: 'BUY' | 'SELL';
  volume: number;
  sl_pips: number;
  rr_ratio: number;
  comment?: string;
}

export interface CalculateApiPayload {
  working_capital: number;
  deposited_cash: number;
  leverage: number;
  risk_method: string;
  custom_risk_pct: number;
  global_sl_mode: string;
  global_sl_pips: number;
  symbol_sl_overrides: Record<string, number>;
}

export const api = {
  async fetchAccount(): Promise<AccountSummary> {
    const res = await fetch('/api/account');
    if (!res.ok) throw new Error('Failed to fetch account info');
    return res.json();
  },

  async fetchInitialCalculate(payload: CalculateApiPayload): Promise<{
    results: Array<{ spec: SymbolSpec }>;
    trade_stats: TradeStats;
    sample_info: SampleSizeInfo;
  }> {
    const res = await fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to fetch calculate data');
    return res.json();
  },

  async executeOrder(payload: ExecuteOrderPayload): Promise<{ success: boolean; message: string; ticket?: number }> {
    const res = await fetch('/api/order/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  },

  async fetchPositions(): Promise<{ positions: OpenPosition[]; count: number }> {
    const res = await fetch('/api/positions');
    if (!res.ok) throw new Error('Failed to fetch positions');
    return res.json();
  },

  async closePosition(ticket: number, volume?: number): Promise<{ success: boolean; message: string }> {
    const res = await fetch('/api/position/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticket, volume }),
    });
    return res.json();
  },

  async modifyPosition(ticket: number, sl?: number, tp?: number): Promise<{ success: boolean; message: string }> {
    const res = await fetch('/api/position/modify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticket, sl, tp }),
    });
    return res.json();
  },

  async closeAllPositions(): Promise<{ results: Array<{ success: boolean; message: string }>; count: number }> {
    const res = await fetch('/api/position/close-all', {
      method: 'POST',
    });
    return res.json();
  },

  async submitManualStats(params: {
    win_rate: number;
    payoff_ratio: number;
    total_trades: number;
    worst_loss: number;
  }): Promise<TradeStats> {
    const res = await fetch('/api/manual-stats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error('Failed to apply manual stats');
    return res.json();
  },

  async uploadTradesCsv(file: File): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload-trades', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to upload CSV');
    }
    return res.json();
  },
};
