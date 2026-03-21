"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useAuth } from "@/hooks/use-auth";
import { LocaleSwitcher } from "@/components/locale-switcher";

const DEV_AUTH_ENABLED = process.env.NEXT_PUBLIC_DEV_AUTH === "true";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const t = useTranslations("login");

  // Regular login form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  // Dev login state
  const [devToken, setDevToken] = useState("");
  const [showDevLogin, setShowDevLogin] = useState(false);

  function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    // Real Cognito login is not wired yet — show message
    setError(t("cognitoNotConfigured"));
  }

  function handleDevLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const trimmed = devToken.replace(/\s+/g, "");
    if (!trimmed) {
      setError(t("pasteJwt"));
      return;
    }

    // Basic JWT structure check (three dot-separated parts)
    const parts = trimmed.split(".");
    if (parts.length !== 3) {
      setError(t("invalidJwt"));
      return;
    }

    login(trimmed);
    router.push("/dashboard");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-6 rounded-lg bg-white p-8 shadow">
        <div className="flex justify-end">
          <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
        </div>
        <h1 className="text-center text-2xl font-bold text-gray-900">
          {t("signIn")}
        </h1>

        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
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
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700"
            >
              {t("password")}
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            {t("signInButton")}
          </button>
        </form>

        <div className="flex justify-between text-sm">
          <Link href="/forgot-password" className="text-blue-600 hover:underline">
            {t("forgotPassword")}
          </Link>
          <Link href="/signup" className="text-blue-600 hover:underline">
            {t("createAccount")}
          </Link>
        </div>

        {/* Dev Login — only shown when NEXT_PUBLIC_DEV_AUTH=true */}
        {DEV_AUTH_ENABLED && (
          <div className="border-t pt-4">
            <button
              type="button"
              onClick={() => setShowDevLogin(!showDevLogin)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              {showDevLogin ? t("hideDevLogin") : t("showDevLogin")}
            </button>

            {showDevLogin && (
              <form onSubmit={handleDevLogin} className="mt-3 space-y-3">
                <p className="text-xs text-gray-500">
                  {t("devLoginInstructions")}
                  <br />
                  <code className="rounded bg-gray-100 px-1 py-0.5 text-xs">
                    cd backend &amp;&amp; python -c &quot;from app.core.security
                    import create_mock_access_token;
                    print(create_mock_access_token(sub=&apos;your-sub&apos;,
                    email=&apos;you@example.com&apos;))&quot;
                  </code>
                </p>
                <textarea
                  value={devToken}
                  onChange={(e) => setDevToken(e.target.value)}
                  rows={3}
                  className="block w-full rounded border border-gray-300 px-3 py-2 font-mono text-xs shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="eyJhbGciOiJIUzI1NiIs..."
                />
                <button
                  type="submit"
                  className="w-full rounded bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-900"
                >
                  {t("devLoginButton")}
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
