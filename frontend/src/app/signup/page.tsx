"use client";

import { useState } from "react";
import Link from "next/link";
import { z } from "zod/v4";
import { useTranslations } from "next-intl";
import { LocaleSwitcher } from "@/components/locale-switcher";

const signupSchema = z
  .object({
    email: z.email("Please enter a valid email address"),
    fullName: z.string().min(1, "Full name is required").max(255),
    password: z
      .string()
      .min(12, "Password must be at least 12 characters")
      .regex(/[A-Z]/, "Password must contain an uppercase letter")
      .regex(/[a-z]/, "Password must contain a lowercase letter")
      .regex(/[0-9]/, "Password must contain a number")
      .regex(/[^A-Za-z0-9]/, "Password must contain a symbol"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type SignupForm = z.infer<typeof signupSchema>;

export default function SignupPage() {
  const [form, setForm] = useState<SignupForm>({
    email: "",
    fullName: "",
    password: "",
    confirmPassword: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const t = useTranslations("signup");

  function handleChange(field: keyof SignupForm, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    // Clear field error on change
    setErrors((prev) => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});

    const result = signupSchema.safeParse(form);
    if (!result.success) {
      const fieldErrors: Record<string, string> = {};
      for (const issue of result.error.issues) {
        const key = issue.path.join(".");
        if (!fieldErrors[key]) fieldErrors[key] = issue.message;
      }
      setErrors(fieldErrors);
      return;
    }

    // Cognito signup not wired yet — show success placeholder
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
            {t("verificationEmailSent")}{" "}
            <strong>{form.email}</strong>.
          </p>
          <Link
            href="/verify-email"
            className="inline-block text-blue-600 hover:underline"
          >
            {t("goToVerification")}
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
          {t("createAccount")}
        </h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field
            id="fullName"
            label={t("fullName")}
            type="text"
            value={form.fullName}
            onChange={(v) => handleChange("fullName", v)}
            error={errors.fullName}
            placeholder={t("fullNamePlaceholder")}
          />
          <Field
            id="email"
            label={t("email")}
            type="email"
            value={form.email}
            onChange={(v) => handleChange("email", v)}
            error={errors.email}
            placeholder="you@example.com"
          />
          <Field
            id="password"
            label={t("password")}
            type="password"
            value={form.password}
            onChange={(v) => handleChange("password", v)}
            error={errors.password}
          />
          <Field
            id="confirmPassword"
            label={t("confirmPassword")}
            type="password"
            value={form.confirmPassword}
            onChange={(v) => handleChange("confirmPassword", v)}
            error={errors.confirmPassword}
          />

          <button
            type="submit"
            className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            {t("signUp")}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600">
          {t("alreadyHaveAccount")}{" "}
          <Link href="/login" className="text-blue-600 hover:underline">
            {t("signIn")}
          </Link>
        </p>
      </div>
    </div>
  );
}

function Field({
  id,
  label,
  type,
  value,
  onChange,
  error,
  placeholder,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        placeholder={placeholder}
        className={`mt-1 block w-full rounded border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 ${
          error
            ? "border-red-300 focus:border-red-500 focus:ring-red-500"
            : "border-gray-300 focus:border-blue-500 focus:ring-blue-500"
        }`}
      />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
