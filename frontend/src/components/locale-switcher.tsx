"use client";

import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import type { CSSProperties } from "react";

export function LocaleSwitcher({ className, style }: { className?: string; style?: CSSProperties }) {
  const router = useRouter();
  const current = useLocale();

  function switchLocale() {
    const next = current === "ar" ? "en" : "ar";
    document.cookie = `NEXT_LOCALE=${next}; path=/; max-age=31536000; SameSite=Lax`;
    router.refresh();
  }

  return (
    <button
      onClick={switchLocale}
      className={className}
      style={style}
      type="button"
      aria-label={current === "ar" ? "Switch to English" : "Switch to Arabic"}
    >
      {current === "ar" ? "EN" : "AR"}
    </button>
  );
}
