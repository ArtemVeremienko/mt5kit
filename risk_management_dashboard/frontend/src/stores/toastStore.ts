import { createSignal, createRoot } from 'solid-js';
import { ToastMessage } from '../types';

function createToastStore() {
  const [toasts, setToasts] = createSignal<ToastMessage[]>([]);
  let seq = 0;

  const addToast = (title: string, message: string, type: 'success' | 'warning' | 'error' | 'info' = 'info') => {
    const id = ++seq;
    setToasts((prev) => [...prev, { id, title, message, type }]);
    setTimeout(() => {
      removeToast(id);
    }, 4000);
  };

  const removeToast = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return {
    toasts,
    addToast,
    removeToast,
  };
}

export const toastStore = createRoot(createToastStore);
