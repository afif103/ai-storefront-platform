"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { LocaleSwitcher } from "@/components/locale-switcher";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const t = useTranslations("forgotPassword");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Cognito forgot-password flow not wired yet
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-8 text-center shadow">
          <div className="flex justify-end">
            <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{t("checkYourEmail")}</h1>
          <p className="text-gray-600">
            {t.rich("resetEmailSent", {
              email,
              bold: (chunks) => <strong>{chunks}</strong>,
            })}
          </p>
          <Link
            href="/login"
            className="inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("backToLoginButton")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-6 rounded-lg bg-white p-8 shadow">
        <div className="flex justify-end">
          <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
        </div>
        <h1 className="text-center text-2xl font-bold text-gray-900">
          {t("title")}
        </h1>
        <p className="text-center text-sm text-gray-600">
          {t("description")}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-gray-700"
            >
              {t("email")}
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="you@example.com"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            {t("sendResetLink")}
          </button>
        </form>

        <p className="text-center text-sm">
          <Link href="/login" className="text-blue-600 hover:underline">
            {t("backToLogin")}
          </Link>
        </p>
      </div>
    </div>
  );
}
