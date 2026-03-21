import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { LocaleSwitcher } from "@/components/locale-switcher";

export default async function VerifyEmailPage() {
  const t = await getTranslations("verifyEmail");

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-8 text-center shadow">
        <div className="flex justify-end">
          <LocaleSwitcher className="text-sm text-gray-500 hover:text-gray-700" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900">
          {t("title")}
        </h1>
        <p className="text-gray-600">
          {t("description")}
        </p>
        <Link
          href="/login"
          className="inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {t("backToLogin")}
        </Link>
      </div>
    </div>
  );
}
