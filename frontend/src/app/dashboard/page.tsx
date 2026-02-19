"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { RequireAuth } from "@/components/require-auth";
import { apiFetch } from "@/lib/api-client";

interface HealthStatus {
  status: string;
  db: string;
  redis: string;
  version: string;
}

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthError, setHealthError] = useState("");

  useEffect(() => {
    async function checkHealth() {
      const result = await apiFetch<HealthStatus>("/api/v1/health");
      if (result.ok) {
        setHealth(result.data);
      } else {
        setHealthError(result.detail);
      }
    }
    checkHealth();
  }, []);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-semibold text-gray-900">Dashboard</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{user?.email}</span>
            <button
              onClick={handleLogout}
              className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <div className="grid gap-6 md:grid-cols-2">
          {/* User Info Card */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Authenticated User
            </h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Subject</dt>
                <dd className="font-mono text-gray-900">{user?.sub}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Email</dt>
                <dd className="text-gray-900">{user?.email}</dd>
              </div>
            </dl>
          </div>

          {/* Backend Health Card */}
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Backend Health
            </h2>
            {healthError ? (
              <p className="text-sm text-red-600">
                Error: {healthError}
              </p>
            ) : health ? (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Status</dt>
                  <dd
                    className={
                      health.status === "ok"
                        ? "font-medium text-green-600"
                        : "font-medium text-red-600"
                    }
                  >
                    {health.status}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Database</dt>
                  <dd className="text-gray-900">{health.db}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Redis</dt>
                  <dd className="text-gray-900">{health.redis}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Version</dt>
                  <dd className="text-gray-900">{health.version}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-gray-400">Checking...</p>
            )}
          </div>
        </div>

        <div className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Catalog
          </h2>
          <div className="flex gap-4">
            <Link
              href="/dashboard/categories"
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Categories
            </Link>
            <Link
              href="/dashboard/products"
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Products
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
