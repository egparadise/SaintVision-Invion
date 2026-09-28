import { useEffect, useRef, useCallback } from 'react';

export interface UseModalA11yOptions {
  isOpen?: boolean;
  onClose: () => void;
  autoFocusFirst?: boolean;
}

/**
 * Custom hook to enforce WCAG 2.1 AA accessibility standards on modals:
 * - Focus Trap (Tab / Shift+Tab cycling within modal) (DEF-S11-03 / WCAG 2.4.3)
 * - Focus Restoration to trigger element on unmount / close (DEF-S11-04 / WCAG 2.4.3)
 * - Modal-scoped Escape key handler with propagation stop (DEF-S11-05 / WCAG 2.1.1)
 */
export function useModalA11y<T extends HTMLElement = HTMLDivElement>({
  isOpen = true,
  onClose,
  autoFocusFirst = true,
}: UseModalA11yOptions) {
  const containerRef = useRef<T>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    // Capture the trigger element that had focus before modal opened
    if (document.activeElement && document.activeElement !== document.body) {
      triggerRef.current = document.activeElement as HTMLElement;
    }

    // Auto-focus the first interactive element or the container
    if (autoFocusFirst && containerRef.current) {
      const focusable = containerRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length > 0) {
        focusable[0].focus();
      } else {
        containerRef.current.focus();
      }
    }

    return () => {
      // Restore focus to the trigger element when the modal is closed / unmounted
      if (triggerRef.current && typeof triggerRef.current.focus === 'function') {
        triggerRef.current.focus();
      }
    };
  }, [isOpen, autoFocusFirst]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent | KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }

      if (e.key === 'Tab') {
        if (!containerRef.current) return;
        const focusable = containerRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    },
    [onClose]
  );

  return { containerRef, handleKeyDown };
}
