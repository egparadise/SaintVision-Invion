import { useEffect, useLayoutEffect, useRef, useCallback } from 'react';

export interface UseModalA11yOptions {
  isOpen?: boolean;
  onClose: () => void;
  autoFocusFirst?: boolean;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  triggerRef?: React.RefObject<HTMLElement | null>;
}

/**
 * Custom hook to enforce WCAG 2.1 AA accessibility standards on modals:
 * - Focus Trap (Tab / Shift+Tab cycling within modal, including container wrap) (DEF-S11-03 / WCAG 2.4.3)
 * - Focus Restoration to trigger element on unmount / close (DEF-S11-04 / WCAG 2.4.3)
 * - Modal-scoped Escape key handler with propagation stop (DEF-S11-05 / WCAG 2.1.1)
 */
export function useModalA11y<T extends HTMLElement = HTMLDivElement>({
  isOpen = true,
  onClose,
  autoFocusFirst = true,
  initialFocusRef,
  triggerRef: explicitTriggerRef,
}: UseModalA11yOptions) {
  const containerRef = useRef<T>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const restoreFocus = useCallback(() => {
    const target = explicitTriggerRef?.current || triggerRef.current;
    if (target && typeof target.focus === 'function') {
      target.focus();
    }
    triggerRef.current = null;
  }, [explicitTriggerRef]);

  useLayoutEffect(() => {
    if (isOpen) {
      if (explicitTriggerRef?.current) {
        triggerRef.current = explicitTriggerRef.current;
      } else if (!triggerRef.current && document.activeElement && document.activeElement !== document.body) {
        triggerRef.current = document.activeElement as HTMLElement;
      }
    }
  }, [isOpen, explicitTriggerRef]);

  useEffect(() => {
    if (!isOpen) {
      restoreFocus();
      return;
    }

    if (autoFocusFirst) {
      if (initialFocusRef?.current) {
        initialFocusRef.current.focus();
      } else if (containerRef.current) {
        const focusable = containerRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          containerRef.current.focus();
        }
      }
    }

    return () => {
      // Restore focus to the trigger element when the modal is closed / unmounted
      restoreFocus();
    };
  }, [isOpen, autoFocusFirst, initialFocusRef, restoreFocus]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent | KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        e.preventDefault();
        onCloseRef.current();
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
          // If currently on first focusable element OR container itself, wrap to last
          if (document.activeElement === first || document.activeElement === containerRef.current) {
            e.preventDefault();
            last.focus();
          }
        } else {
          // If currently on last focusable element OR container itself, wrap to first
          if (document.activeElement === last || document.activeElement === containerRef.current) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    },
    []
  );

  return { containerRef, handleKeyDown };
}
