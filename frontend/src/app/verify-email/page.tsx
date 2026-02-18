import Link from "next/link";

export default function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-4 rounded-lg bg-white p-8 text-center shadow">
        <h1 className="text-2xl font-bold text-gray-900">
          Verify Your Email
        </h1>
        <p className="text-gray-600">
          Check your inbox for a verification link from Cognito. This page will
          be functional once AWS Cognito is configured (M1 task 1.11).
        </p>
        <Link
          href="/login"
          className="inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Back to Login
        </Link>
      </div>
    </div>
  );
}
