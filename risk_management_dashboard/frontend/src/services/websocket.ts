import { marketStore } from '../stores/marketStore';
import { accountStore } from '../stores/accountStore';
import { positionsStore } from '../stores/positionsStore';
import { preferencesStore } from '../stores/preferencesStore';

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectTimeout: number | null = null;
  private isExplicitDisconnect: boolean = false;

  connect() {
    this.isExplicitDisconnect = false;

    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        return;
      }
      // Detach handlers from dead/closing socket
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      this.ws.onopen = null;
      this.ws = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;
    const socket = new WebSocket(wsUrl);
    this.ws = socket;

    socket.onopen = () => {
      if (this.ws !== socket) return;
      accountStore.setIsConnected(true);
      this.sendRateUpdate(preferencesStore.turboMode() ? 500 : 2000);
    };

    socket.onmessage = (event) => {
      if (this.ws !== socket) return;
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

        if (data.trade_stats) {
          marketStore.setTradeStats(data.trade_stats);
        }

        if (data.sample_info) {
          marketStore.setSampleInfo(data.sample_info);
        }
      } catch (e) {
        console.error('WebSocket message parsing error:', e);
      }
    };

    socket.onclose = () => {
      if (this.ws !== socket) return;
      accountStore.setIsConnected(false);
      this.ws = null;

      if (!this.isExplicitDisconnect && !this.reconnectTimeout) {
        this.reconnectTimeout = window.setTimeout(() => {
          this.reconnectTimeout = null;
          this.connect();
        }, 3000);
      }
    };

    socket.onerror = (e) => {
      if (this.ws !== socket) return;
      console.warn('WebSocket error:', e);
      socket.close();
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
    this.isExplicitDisconnect = true;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      const socket = this.ws;
      this.ws = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.onmessage = null;
      socket.onopen = null;
      socket.close();
    }
  }
}

export const wsService = new WebSocketService();
