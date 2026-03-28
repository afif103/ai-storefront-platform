"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { cognitoConfirmForgotPassword } from "@/lib/cognito";

const COGNITO_MOCK = process.env.NEXT_PUBLIC_COGNITO_MOCK === "true";

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useTranslations("resetPassword");

  const email = searchParams.get("email") ?? "";

  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (COGNITO_MOCK) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-8 text-center shadow">
          <div className="flex justify-end">
            <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            {t("devModeTitle")}
          </h1>
          <p className="text-sm text-gray-600">{t("devModeDescription")}</p>
          <Link
            href="/login"
            className="inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("devModeLoginLink")}
          </Link>
        </div>
      </div>
    );
  }

  if (!email) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-8 text-center shadow">
          <div className="flex justify-end">
            <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
          </div>
          <p className="text-sm text-gray-600">{t("missingEmail")}</p>
          <Link
            href="/forgot-password"
            className="inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("backToForgotPassword")}
          </Link>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError(t("passwordsMismatch"));
      return;
    }

    setIsSubmitting(true);
    try {
      await cognitoConfirmForgotPassword(email, code, newPassword);
      router.push("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("resetFailed"));
    } finally {
      setIsSubmitting(false);
    }
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
          {t("description", { email })}
        </p>

        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="code"
              className="block text-sm font-medium text-gray-700"
            >
              {t("code")}
            </label>
            <input
              id="code"
              type="text"
              inputMode="numeric"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              maxLength={6}
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 font-mono text-sm tracking-widest shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder={t("codePlaceholder")}
            />
          </div>

          <div>
            <label
              htmlFor="newPassword"
              className="block text-sm font-medium text-gray-700"
            >
              {t("newPassword")}
            </label>
            <input
              id="newPassword"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label
              htmlFor="confirmPassword"
              className="block text-sm font-medium text-gray-700"
            >
              {t("confirmPassword")}
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {isSubmitting ? t("resetting") : t("resetButton")}
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
