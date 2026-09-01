import { onMount } from 'solid-js';

declare module 'solid-js' {
  namespace JSX {
    interface Directives {
      autofocus: boolean | undefined;
    }
  }
}

/**
 * Idiomatic Solid.js Custom Directive for synchronous autofocus and text selection on mount.
 * Usage: use:autofocus={condition}
 */
export function autofocus(el: HTMLElement, accessor: () => boolean | undefined) {
  onMount(() => {
    if (accessor()) {
      if ('focus' in el && typeof (el as HTMLInputElement).focus === 'function') {
        (el as HTMLInputElement).focus({ preventScroll: true });
      }
      if ('select' in el && typeof (el as HTMLInputElement).select === 'function') {
        (el as HTMLInputElement).select();
      }
    }
  });
}
