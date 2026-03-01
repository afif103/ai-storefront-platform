"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface CartItem {
  catalogItemId: string;
  name: string;
  priceAmount: string;
  currency: string;
  qty: number;
}

function storageKey(slug: string): string {
  return `cart:${slug}`;
}

function readStoredCart(slug: string): CartItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(storageKey(slug));
    return raw ? (JSON.parse(raw) as CartItem[]) : [];
  } catch {
    return [];
  }
}

/**
 * In-memory cart persisted to sessionStorage, keyed by storefront slug.
 *
 * Upserts by catalogItemId (adding an existing item increments qty).
 */
export function useCart(slug: string) {
  const [items, setItems] = useState<CartItem[]>(() => readStoredCart(slug));
  const hydrated = useRef(false);

  // Mark hydrated after first render
  useEffect(() => {
    hydrated.current = true;
  }, []);

  // Sync to sessionStorage on every change (skip initial hydration)
  useEffect(() => {
    if (!hydrated.current) return;
    sessionStorage.setItem(storageKey(slug), JSON.stringify(items));
  }, [items, slug]);

  const addItem = useCallback(
    (product: Omit<CartItem, "qty">, qty: number = 1) => {
      setItems((prev) => {
        const idx = prev.findIndex(
          (i) => i.catalogItemId === product.catalogItemId
        );
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = { ...updated[idx], qty: updated[idx].qty + qty };
          return updated;
        }
        return [...prev, { ...product, qty }];
      });
    },
    []
  );

  const removeItem = useCallback((catalogItemId: string) => {
    setItems((prev) => prev.filter((i) => i.catalogItemId !== catalogItemId));
  }, []);

  const clearCart = useCallback(() => {
    setItems([]);
  }, []);

  const totalItems = items.reduce((sum, i) => sum + i.qty, 0);

  return { items, addItem, removeItem, clearCart, totalItems };
}
