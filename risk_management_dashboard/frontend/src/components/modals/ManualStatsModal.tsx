import { Component, createSignal } from 'solid-js';
import { marketStore } from '../../stores/marketStore';
import { api } from '../../services/api';
import { toastStore } from '../../stores/toastStore';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const ManualStatsModal: Component<Props> = (props) => {
  const tradeStats = marketStore.tradeStats;

  const [winRate, setWinRate] = createSignal<number>((tradeStats().win_rate || 0.55) * 100);
  const [payoffRatio, setPayoffRatio] = createSignal<number>(tradeStats().payoff_ratio || 1.5);
  const [totalTrades, setTotalTrades] = createSignal<number>(tradeStats().total_trades || 250);
  const [worstLoss, setWorstLoss] = createSignal<number>(tradeStats().worst_loss || 100.0);
  const [isSubmitting, setIsSubmitting] = createSignal<boolean>(false);

  const handleSubmit = async (e: Event) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      const res = await api.submitManualStats({
        win_rate: winRate() / 100.0,
        payoff_ratio: payoffRatio(),
        total_trades: totalTrades(),
        worst_loss: worstLoss(),
      });
      marketStore.setTradeStats(res);
      if (res.sample_info) {
        marketStore.setSampleInfo(res.sample_info);
      }
      toastStore.addToast('Strategy Profile Updated', 'Applied manual strategy parameters', 'success');
      props.onClose();
    } catch (err: any) {
      toastStore.addToast('Error', err.message || 'Failed to update manual strategy parameters', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div class="modal-backdrop" onClick={props.onClose}>
      <div class="modal-card" onClick={(e) => e.stopPropagation()}>
        <div class="modal-header">
          <div class="modal-title-group">
            <span class="modal-icon">⚙️</span>
            <h3 class="modal-title">Manual Strategy Profile Parameters</h3>
          </div>
          <button class="modal-close-btn" onClick={props.onClose}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label" for="param-win-rate">
                WIN RATE (%):
              </label>
              <input
                id="param-win-rate"
                type="number"
                class="control-input"
                step="0.5"
                min="1"
                max="99"
                value={winRate()}
                onInput={(e) => setWinRate(parseFloat(e.currentTarget.value) || 50)}
              />
            </div>

            <div class="form-group">
              <label class="form-label" for="param-payoff">
                PAYOFF RATIO (Avg Win / Avg Loss):
              </label>
              <input
                id="param-payoff"
                type="number"
                class="control-input"
                step="0.05"
                min="0.1"
                max="20"
                value={payoffRatio()}
                onInput={(e) => setPayoffRatio(parseFloat(e.currentTarget.value) || 1.5)}
              />
            </div>

            <div class="form-group">
              <label class="form-label" for="param-trades">
                TOTAL TRADES SAMPLE SIZE:
              </label>
              <input
                id="param-trades"
                type="number"
                class="control-input"
                step="10"
                min="10"
                value={totalTrades()}
                onInput={(e) => setTotalTrades(parseInt(e.currentTarget.value, 10) || 100)}
              />
            </div>

            <div class="form-group">
              <label class="form-label" for="param-worst-loss">
                WORST SINGLE LOSS ($):
              </label>
              <input
                id="param-worst-loss"
                type="number"
                class="control-input"
                step="10"
                min="1"
                value={worstLoss()}
                onInput={(e) => setWorstLoss(parseFloat(e.currentTarget.value) || 100)}
              />
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-ghost" onClick={props.onClose}>
              Cancel
            </button>
            <button type="submit" class="btn-primary" disabled={isSubmitting()}>
              {isSubmitting() ? 'Applying...' : 'Apply Parameters'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
