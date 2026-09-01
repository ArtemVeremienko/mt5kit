import { StepRule } from '../types';

export interface AssetStepRule {
  pipSize: number;
  digits: number;
  normalStep: number;
  fastStep: number;
  precisionStep: number;
  unitLabel: string;
  stopsLevelPips?: number;
}

/**
 * Returns symbol-specific stepping rules, precision, and multiplier increments.
 * Prioritizes backend-computed StepRule (from broker MT5 metadata) with zero guesswork.
 */
export function getAssetStepRule(
  symbol: string,
  digits: number,
  pipSizeFromBackend?: number,
  backendStepRule?: StepRule
): AssetStepRule {
  if (backendStepRule) {
    return {
      pipSize: backendStepRule.pip_size,
      digits: backendStepRule.digits,
      normalStep: backendStepRule.normal_step,
      fastStep: backendStepRule.fast_step,
      precisionStep: backendStepRule.precision_step,
      unitLabel: backendStepRule.unit_label,
      stopsLevelPips: backendStepRule.stops_level_pips,
    };
  }

  const sym = symbol.toUpperCase();

  // 1. Forex JPY Pairs (USDJPY, EURJPY, etc.)
  if (sym.includes('JPY') && digits === 3) {
    return {
      pipSize: 0.01,
      digits: 3,
      normalStep: 0.01,
      fastStep: 0.10,
      precisionStep: 0.001,
      unitLabel: 'pips',
    };
  }

  // 2. Forex Standard Pairs (EURUSD, GBPUSD, AUDUSD, etc.)
  if (digits === 5 || (digits === 4 && !sym.includes('XAU'))) {
    const pip = pipSizeFromBackend || 0.0001;
    return {
      pipSize: pip,
      digits: digits,
      normalStep: pip,
      fastStep: pip * 10,
      precisionStep: Math.pow(10, -digits),
      unitLabel: 'pips',
    };
  }

  // 3. Precious Metals (Gold - XAUUSD, XAUEUR)
  if (sym.includes('XAU') || sym.includes('GOLD')) {
    return {
      pipSize: 0.10,
      digits: 2,
      normalStep: 0.50,
      fastStep: 5.00,
      precisionStep: 0.05,
      unitLabel: 'pts',
    };
  }

  // Fallback Generic Asset
  const fallbackPip = pipSizeFromBackend || Math.pow(10, -digits) * 10;
  return {
    pipSize: fallbackPip,
    digits: digits,
    normalStep: fallbackPip,
    fastStep: fallbackPip * 10,
    precisionStep: Math.pow(10, -digits),
    unitLabel: [3, 5].includes(digits) ? 'pips' : 'pts',
  };
}

/**
 * Safely steps a price up or down with exact decimal rounding.
 */
export function stepPrice(
  currentPrice: number,
  direction: 'UP' | 'DOWN',
  rule: AssetStepRule,
  event?: KeyboardEvent | MouseEvent
): number {
  let step = rule.normalStep;
  if (event) {
    if (event.shiftKey) {
      step = rule.fastStep;
    } else if (event.altKey) {
      step = rule.precisionStep;
    }
  }

  const mult = direction === 'UP' ? 1 : -1;
  const result = currentPrice + mult * step;
  return Math.max(0, parseFloat(result.toFixed(rule.digits)));
}
