import { marketStore } from '../stores/marketStore';
import { accountStore } from '../stores/accountStore';
import { positionsStore } from '../stores/positionsStore';
import { preferencesStore } from '../stores/preferencesStore';

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectTimeout: number | null = null;

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      accountStore.setIsConnected(true);
      this.sendRateUpdate(preferencesStore.turboMode() ? 500 : 2000);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.account) {
          accountStore.updateAccount(data.account);
        }

        if (data.symbols && Array.isArray(data.symbols) && data.symbols.length > 0) {
          marketStore.setRawSymbols(data.symbols);
        }

        if (data.positions && Array.isArray(data.positions)) {
          positionsStore.setPositions(data.positions);
        }
      } catch (e) {
        console.error('WebSocket message parsing error:', e);
      }
    };

    this.ws.onclose = () => {
      accountStore.setIsConnected(false);
      this.ws = null;
      if (!this.reconnectTimeout) {
        this.reconnectTimeout = window.setTimeout(() => {
          this.reconnectTimeout = null;
          this.connect();
        }, 3000);
      }
    };

    this.ws.onerror = (e) => {
      console.warn('WebSocket error:', e);
      if (this.ws) {
        this.ws.close();
      }
    };
  }

  sendRateUpdate(intervalMs: number) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          action: 'set_rate',
          interval_ms: intervalMs,
        })
      );
    }
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsService = new WebSocketService();
