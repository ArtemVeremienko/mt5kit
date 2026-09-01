import { Component, For } from 'solid-js';
import { toastStore } from '../../stores/toastStore';

export const ToastContainer: Component = () => {
  return (
    <div class="toast-stack">
      <For each={toastStore.toasts()}>
        {(t) => (
          <div class={`toast-card toast-${t.type}`} onClick={() => toastStore.removeToast(t.id)}>
            <div class="toast-header">
              <span class="toast-title">{t.title}</span>
              <button class="toast-close-btn">✕</button>
            </div>
            <div class="toast-body">{t.message}</div>
          </div>
        )}
      </For>
    </div>
  );
};
