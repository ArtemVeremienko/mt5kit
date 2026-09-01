import { SymbolSpec, CalculatedSymbolResult, TradeStats, ModelComparison, LotCalculation } from '../types';

export function computeLocalRiskForResult(
  spec: SymbolSpec,
  workingCapital: number,
  depositedCash: number,
  leverage: number,
  riskMethod: string,
  customRiskPct: number,
  slMode: string,
  symbolSlOverrides: Record<string, number>,
  tradeStats: Partial<TradeStats>
): CalculatedSymbolResult {
  const symbol = spec.symbol;
  const digits = spec.digits !== undefined ? spec.digits : 5;
  const point = spec.point || 0.00001;
  const pipMultiplier = digits === 3 || digits === 5 ? 10.0 : 1.0;
  const pipSize = spec.pip_size || point * pipMultiplier;
  const bid = spec.bid || 0;
  const ask = spec.ask || 0;
  const spreadPips = spec.spread_pips !== undefined ? spec.spread_pips : (ask - bid) / (pipSize || 0.0001);
  const adr14 = spec.adr_14_pips || 65.0;
  const atr14 = spec.atr_14_pips || adr14 * 1.05;

  // 1. SL Pips determination
  let slPips: number;
  if (symbolSlOverrides && symbolSlOverrides[symbol] !== undefined && !isNaN(Number(symbolSlOverrides[symbol]))) {
    slPips = Math.max(1.0, Number(symbolSlOverrides[symbol]));
  } else if (slMode === '1/4 ADR') {
    slPips = Math.max(1.0, Math.round(adr14 * 0.25 * 10) / 10);
  } else if (slMode === '1/3 ADR') {
    slPips = Math.max(1.0, Math.round(adr14 * (1.0 / 3.0) * 10) / 10);
  } else if (slMode === '1/2 ADR') {
    slPips = Math.max(1.0, Math.round(adr14 * 0.5 * 10) / 10);
  } else if (slMode === '1 ADR') {
    slPips = Math.max(1.0, Math.round(adr14 * 10) / 10);
  } else if (slMode === '1 ATR') {
    slPips = Math.max(1.0, Math.round(atr14 * 10) / 10);
  } else {
    slPips = 20.0;
  }

  // 2. Target Risk %
  let targetRiskPct = 1.0;
  if (riskMethod === 'fractional') {
    targetRiskPct = Math.max(0.01, customRiskPct || 1.0);
  } else if (riskMethod === 'kelly_full') {
    targetRiskPct = (tradeStats.kelly_full || 0.05) * 100.0;
  } else if (riskMethod === 'kelly_half') {
    targetRiskPct = (tradeStats.kelly_half || 0.025) * 100.0;
  } else if (riskMethod === 'kelly_quarter') {
    targetRiskPct = (tradeStats.kelly_quarter || 0.0125) * 100.0;
  } else if (riskMethod === 'optimal_f_full') {
    targetRiskPct = (tradeStats.optimal_f || 0.05) * 100.0;
  } else if (riskMethod === 'optimal_f_half') {
    targetRiskPct = (tradeStats.optimal_f_half || 0.025) * 100.0;
  } else if (riskMethod === 'optimal_f_quarter') {
    targetRiskPct = (tradeStats.optimal_f_quarter || 0.0125) * 100.0;
  }

  const workingCap = workingCapital || 100.0;
  const targetRiskAmount = workingCap * (targetRiskPct / 100.0);
  const pipValPerLot = spec.pip_value_per_lot > 0 ? spec.pip_value_per_lot : 10.0;
  const riskPerLot = slPips * pipValPerLot;
  const exactLot = riskPerLot > 0 ? targetRiskAmount / riskPerLot : 0.0;

  // 3. Broker Volume Clamping
  const volumeMin = spec.volume_min || 0.01;
  const volumeMax = spec.volume_max || 100.0;
  const volumeStep = spec.volume_step || 0.01;

  const steps = Math.round(exactLot / volumeStep);
  const steppedLot = Math.round(steps * volumeStep * 1000000) / 1000000;

  let executableLot = steppedLot;
  let isClampedMin = false;
  let isClampedMax = false;

  if (steppedLot < volumeMin) {
    executableLot = volumeMin;
    isClampedMin = true;
  } else if (steppedLot > volumeMax) {
    executableLot = volumeMax;
    isClampedMax = true;
  }

  const decimals = volumeStep < 1 ? Math.max(0, Math.ceil(-Math.log10(volumeStep))) : 2;
  executableLot = parseFloat(executableLot.toFixed(decimals));

  // 4. Effective Risk
  const effectiveRiskAmount = executableLot * slPips * pipValPerLot;
  const effectiveRiskPct = workingCap > 0 ? (effectiveRiskAmount / workingCap) * 100.0 : 0.0;

  // 5. Margin Calculation
  const contractSize = spec.trade_contract_size || 100000.0;
  const lev = leverage > 0 ? leverage : 300.0;
  const marketPrice = bid > 0 ? bid : ask > 0 ? ask : 1.0;
  const symUpper = symbol.toUpperCase();

  let requiredMargin = 0.0;
  if (symUpper.includes('JP225') || symUpper.includes('JPN225') || symUpper.includes('NIKKEI')) {
    const notionalJpy = executableLot * contractSize * marketPrice;
    requiredMargin = notionalJpy / 159.5;
  } else if (symUpper.includes('DE40') || symUpper.includes('GER40') || symUpper.includes('DAX')) {
    const notionalEur = executableLot * contractSize * marketPrice;
    requiredMargin = (notionalEur * 1.16) / (lev / 30.0);
  } else if (spec.currency_base === 'USD' || symUpper.startsWith('USD')) {
    requiredMargin = (executableLot * contractSize) / lev;
  } else {
    requiredMargin = (executableLot * contractSize * marketPrice) / lev;
  }
  requiredMargin = Math.round(requiredMargin * 100) / 100;

  const depCash = depositedCash > 0 ? depositedCash : 20.0;
  const marginUtilPct = depCash > 0 ? (requiredMargin / depCash) * 100.0 : 0.0;
  const isMarginExceeded = marginUtilPct > 100.0;
  const marginStatus: 'healthy' | 'warning' | 'exceeded' = isMarginExceeded ? 'exceeded' : marginUtilPct > 70.0 ? 'warning' : 'healthy';

  // Helper for multi-model comparison
  const calcCompare = (riskPct: number): ModelComparison => {
    const tAmt = workingCap * (riskPct / 100.0);
    const exLot = riskPerLot > 0 ? tAmt / riskPerLot : 0.0;
    const st = Math.round(exLot / volumeStep) * volumeStep;
    const cl = Math.max(volumeMin, Math.min(volumeMax, st));
    const cLot = parseFloat(cl.toFixed(decimals));
    let m = 0;
    if (spec.currency_base === 'USD' || symUpper.startsWith('USD')) {
      m = (cLot * contractSize) / lev;
    } else {
      m = (cLot * contractSize * marketPrice) / lev;
    }
    return {
      lot: cLot,
      risk_pct: riskPct,
      risk_amount: cLot * slPips * pipValPerLot,
      margin: Math.round(m * 100) / 100,
    };
  };

  const comparison = {
    fractional_1pct: calcCompare(1.0),
    half_kelly: calcCompare(Math.max(0.1, (tradeStats.kelly_half || 0.025) * 100)),
    half_optimal_f: calcCompare(Math.max(0.1, (tradeStats.optimal_f_half || 0.025) * 100)),
  };

  const specFormatted: SymbolSpec = {
    ...spec,
    bid_display: bid.toFixed(digits),
    ask_display: ask.toFixed(digits),
    spread_display: spreadPips.toFixed(1),
    adr_display: adr14.toFixed(1),
    atr_display: atr14.toFixed(1),
  };

  const calcFormatted: LotCalculation = {
    symbol: symbol,
    working_capital: workingCap,
    deposited_cash: depCash,
    leverage: lev,
    risk_method: riskMethod,
    target_risk_pct: targetRiskPct,
    target_risk_amount: targetRiskAmount,
    sl_pips: slPips,
    pip_value_per_lot: pipValPerLot,
    pip_val_display: pipValPerLot.toFixed(2),
    exact_lot: exactLot,
    exact_lot_display: exactLot.toFixed(4),
    executable_lot: executableLot,
    lot_display: executableLot.toFixed(decimals),
    effective_risk_amount: effectiveRiskAmount,
    effective_risk_pct: effectiveRiskPct,
    effective_risk_pct_display: effectiveRiskPct.toFixed(2),
    risk_display: `$${effectiveRiskAmount.toFixed(2)} (${effectiveRiskPct.toFixed(2)}%)`,
    is_clamped_to_min: isClampedMin,
    is_clamped_to_max: isClampedMax,
    min_volume: volumeMin,
    max_volume: volumeMax,
    volume_step: volumeStep,
    contract_size: contractSize,
    market_price: marketPrice,
    required_margin: requiredMargin,
    required_margin_display: requiredMargin.toFixed(2),
    margin_utilization_pct: marginUtilPct,
    margin_utilization_display: marginUtilPct.toFixed(0),
    is_margin_exceeded: isMarginExceeded,
    margin_status: marginStatus,
  };

  return {
    spec: specFormatted,
    calc: calcFormatted,
    comparison: comparison,
  };
}
