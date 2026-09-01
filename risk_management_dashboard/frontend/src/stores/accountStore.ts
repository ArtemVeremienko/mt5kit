import { createSignal, createRoot } from 'solid-js';
import { AccountSummary } from '../types';

function createAccountStore() {
  const [account, setAccount] = createSignal<AccountSummary>({
    balance: 27.0,
    equity: 27.0,
    margin: 0.0,
    free_margin: 27.0,
    margin_level: 0.0,
    leverage: 300.0,
    profit: 0.0,
    currency: 'USD',
    server: 'MetaQuotes-Demo',
    name: 'Demo Account',
    login: 10000001,
  });

  const [isConnected, setIsConnected] = createSignal<boolean>(false);

  const updateAccount = (data: Partial<AccountSummary>) => {
    setAccount((prev) => ({ ...prev, ...data }));
  };

  return {
    account,
    setAccount,
    updateAccount,
    isConnected,
    setIsConnected,
  };
}

export const accountStore = createRoot(createAccountStore);
