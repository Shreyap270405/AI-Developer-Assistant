import { useState, useCallback } from 'react';

/**
 * useToast — manages a transient notification message.
 *
 * Returns:
 *   toast    – { message, type } | null
 *   showToast(message, type?) – displays a toast for 5 s
 *   closeToast()             – dismisses immediately
 */
export function useToast() {
  const [toast, setToast] = useState(null);

  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  }, []);

  const closeToast = useCallback(() => setToast(null), []);

  return { toast, showToast, closeToast };
}
