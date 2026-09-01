import { Component, createSignal } from 'solid-js';
import { api } from '../../services/api';
import { marketStore } from '../../stores/marketStore';
import { toastStore } from '../../stores/toastStore';
import { preferencesStore } from '../../stores/preferencesStore';
import { accountStore } from '../../stores/accountStore';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const CsvUploadModal: Component<Props> = (props) => {
  const [selectedFile, setSelectedFile] = createSignal<File | null>(null);
  const [isUploading, setIsUploading] = createSignal<boolean>(false);

  const handleUpload = async (e: Event) => {
    e.preventDefault();
    const file = selectedFile();
    if (!file) {
      alert('Please select a CSV file first');
      return;
    }

    try {
      setIsUploading(true);
      const res = await api.uploadTradesCsv(file);
      toastStore.addToast('CSV Import Successful', res.message || 'Imported trade history', 'success');

      // Refresh calculate specs and stats from backend
      const calcData = await api.fetchInitialCalculate({
        working_capital: preferencesStore.workingCapital(),
        deposited_cash: accountStore.account().balance || 20.0,
        leverage: accountStore.account().leverage || 300.0,
        risk_method: preferencesStore.riskMethod(),
        custom_risk_pct: preferencesStore.customRiskPct(),
        global_sl_mode: preferencesStore.slMode(),
        global_sl_pips: 20.0,
        symbol_sl_overrides: preferencesStore.slOverrides(),
      });

      marketStore.setTradeStats(calcData.trade_stats);
      marketStore.setSampleInfo(calcData.sample_info);
      props.onClose();
    } catch (err: any) {
      toastStore.addToast('CSV Upload Failed', err.message || 'Could not parse trade file', 'error');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div class="modal-backdrop" onClick={props.onClose}>
      <div class="modal-card" onClick={(e) => e.stopPropagation()}>
        <div class="modal-header">
          <div class="modal-title-group">
            <span class="modal-icon">📁</span>
            <h3 class="modal-title">Import Closed Trades CSV</h3>
          </div>
          <button class="modal-close-btn" onClick={props.onClose}>
            ✕
          </button>
        </div>

        <form onSubmit={handleUpload}>
          <div class="modal-body">
            <p class="text-secondary text-sm">
              Upload a standard MT5/MT4 closed trade report (CSV) containing columns:
              <code>Profit</code>, <code>Type</code>, <code>Volume</code>, <code>Symbol</code>.
            </p>

            <div class="file-upload-dropzone">
              <input
                type="file"
                accept=".csv"
                id="csv-file-input"
                class="file-input-hidden"
                onChange={(e) => {
                  if (e.currentTarget.files && e.currentTarget.files[0]) {
                    setSelectedFile(e.currentTarget.files[0]);
                  }
                }}
              />
              <label for="csv-file-input" class="dropzone-label">
                <span class="dropzone-icon">📄</span>
                <span class="dropzone-text">
                  {selectedFile() ? selectedFile()!.name : 'Click to select or drag & drop CSV file'}
                </span>
                <span class="dropzone-sub">Accepts .csv format (max 5MB)</span>
              </label>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-ghost" onClick={props.onClose}>
              Cancel
            </button>
            <button type="submit" class="btn-primary" disabled={!selectedFile() || isUploading()}>
              {isUploading() ? 'Processing...' : 'Upload & Recalculate'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
