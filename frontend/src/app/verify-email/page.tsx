"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { cognitoConfirmSignUp } from "@/lib/cognito";

const COGNITO_MOCK = process.env.NEXT_PUBLIC_COGNITO_MOCK === "true";

export default function VerifyEmailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const t = useTranslations("verifyEmail");

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
          <p className="text-gray-600">{t("devModeNotNeeded")}</p>
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
          <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
          <p className="text-gray-600">{t("missingEmail")}</p>
          <Link
            href="/signup"
            className="inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("backToSignup")}
          </Link>
        </div>
      </div>
    );
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await cognitoConfirmSignUp(email, code);
      router.push("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("verifyFailed"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-8 text-center shadow">
        <div className="flex justify-end">
          <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
        <p className="text-gray-600">
          {t("enterCode")} <strong>{email}</strong>
        </p>

        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleVerify} className="space-y-4">
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            placeholder={t("codePlaceholder")}
            className="block w-full rounded border border-gray-300 px-3 py-2 text-center text-lg tracking-widest shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {t("verify")}
          </button>
        </form>

        <Link
          href="/login"
          className="inline-block text-sm text-blue-600 hover:underline"
        >
          {t("backToLogin")}
        </Link>
      </div>
    </div>
  );
}
