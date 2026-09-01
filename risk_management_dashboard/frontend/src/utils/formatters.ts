export function formatCurrency(val: number | undefined | null, decimals = 2): string {
  if (val === undefined || val === null || isNaN(val)) return '$0.00';
  const isNegative = val < 0;
  const absVal = Math.abs(val);
  const formatted = absVal.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return isNegative ? `-$${formatted}` : `$${formatted}`;
}

export function formatPercent(val: number | undefined | null, decimals = 1): string {
  if (val === undefined || val === null || isNaN(val)) return '0.0%';
  return `${val.toFixed(decimals)}%`;
}

export function formatNumber(val: number | undefined | null, decimals = 2): string {
  if (val === undefined || val === null || isNaN(val)) return '0.00';
  return val.toFixed(decimals);
}
