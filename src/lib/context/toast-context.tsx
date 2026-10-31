"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { CheckCircle2, X, Heart, ShoppingBag } from "lucide-react";

// ============================================================
// Types
// ============================================================

export interface Toast {
  id: string;
  type: "cart" | "wishlist" | "success" | "error";
  message: string;
  actionLabel?: string;
  actionHref?: string;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

// ============================================================
// Context
// ============================================================

const ToastContext = createContext<ToastContextValue | null>(null);

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = `toast-${++toastCounter}-${Date.now()}`;
      setToasts((prev) => [...prev, { ...toast, id }]);

      // Auto-dismiss after 4 seconds
      setTimeout(() => {
        removeToast(id);
      }, 4000);
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      {/* Toast Container */}
      <div
        className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] flex flex-col-reverse gap-2 w-[calc(100%-2rem)] max-w-sm pointer-events-none"
        aria-live="polite"
        aria-label="Notifications"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto animate-fade-in-up bg-charcoal text-cream rounded-xl shadow-2xl shadow-charcoal/20 flex items-center gap-3 px-4 py-3.5"
          >
            {/* Icon */}
            <div className="flex-shrink-0">
              {toast.type === "cart" ? (
                <ShoppingBag className="w-4 h-4 text-terracotta" />
              ) : toast.type === "wishlist" ? (
                <Heart className="w-4 h-4 text-terracotta" fill="currentColor" />
              ) : toast.type === "error" ? (
                <X className="w-4 h-4 text-rust" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-green-400" />
              )}
            </div>

            {/* Message */}
            <span className="text-sm text-cream/90 flex-1">{toast.message}</span>

            {/* Action */}
            {toast.actionLabel && (
              <a
                href={toast.actionHref ?? "#"}
                className="text-xs font-medium text-terracotta hover:text-warm-beige transition-colors flex-shrink-0 underline-offset-2 hover:underline"
              >
                {toast.actionLabel}
              </a>
            )}

            {/* Dismiss */}
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 p-0.5 text-cream/65 hover:text-cream transition-colors"
              aria-label="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a <ToastProvider>");
  }
  return ctx;
}