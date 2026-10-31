"use client";

import { type ReactNode } from "react";
import { CartProvider } from "@/lib/context/cart-context";
import { WishlistProvider } from "@/lib/context/wishlist-context";
import { ToastProvider } from "@/lib/context/toast-context";
import { CatalogProvider } from "@/lib/context/catalog-context";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <CatalogProvider>
        <CartProvider>
          <WishlistProvider>{children}</WishlistProvider>
        </CartProvider>
      </CatalogProvider>
    </ToastProvider>
  );
}
