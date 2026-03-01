"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import { useVisit } from "@/hooks/use-visit";

interface PledgeResponse {
  id: string;
  pledge_number: string;
  amount: string;
  currency: string;
  status: string;
  created_at: string;
}

export default function PledgePage() {
  const params = useParams();
  const slug = params.slug as string;
  const { visitId } = useVisit(slug);

  const [pledgorName, setPledgorName] = useState("");
  const [pledgorPhone, setPledgorPhone] = useState("");
  const [pledgorEmail, setPledgorEmail] = useState("");
  const [amount, setAmount] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<PledgeResponse | null>(null);

  // Tomorrow as minimum date
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const minDate = tomorrow.toISOString().split("T")[0];

  function formatAmount(raw: string): string {
    const num = parseFloat(raw);
    if (isNaN(num) || num <= 0) return raw;
    return num.toFixed(3);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const formatted = formatAmount(amount);
    if (parseFloat(formatted) <= 0 || isNaN(parseFloat(formatted))) {
      setError("Please enter a valid amount greater than 0.");
      return;
    }

    if (!targetDate) {
      setError("Please select a target date.");
      return;
    }

    setSubmitting(true);

    const result = await apiFetch<PledgeResponse>(
      `/api/v1/storefront/${slug}/pledges`,
      {
        method: "POST",
        body: JSON.stringify({
          pledgor_name: pledgorName,
          pledgor_phone: pledgorPhone || undefined,
          pledgor_email: pledgorEmail || undefined,
          amount: formatted,
          target_date: targetDate,
          visit_id: visitId || undefined,
        }),
      }
    );

    setSubmitting(false);
    if (result.ok) {
      setSuccess(result.data);
    } else {
      setError(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail));
    }
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-md rounded-lg border border-green-300 bg-green-50 p-8 text-center">
          <h2 className="text-lg font-bold text-green-800">Pledge Received!</h2>
          <p className="mt-2 text-sm text-green-700">
            Pledge number: <span className="font-mono font-bold">{success.pledge_number}</span>
          </p>
          <p className="mt-1 text-sm text-green-700">
            Amount: {success.amount} {success.currency}
          </p>
          <p className="mt-1 text-sm text-green-700">Status: {success.status}</p>
          <Link
            href={`/storefront/${slug}`}
            className="mt-6 inline-block rounded-lg bg-green-700 px-6 py-2 text-sm font-medium text-white hover:bg-green-800"
          >
            Back to Store
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="mx-auto max-w-lg">
        <Link
          href={`/storefront/${slug}`}
          className="mb-4 inline-block text-sm text-blue-600 hover:underline"
        >
          &larr; Back to store
        </Link>

        <h1 className="mb-6 text-2xl font-bold text-gray-900">Make a Pledge</h1>

        <form onSubmit={handleSubmit} className="rounded-lg border bg-white p-6">
          {error && (
            <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Your Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              maxLength={255}
              value={pledgorName}
              onChange={(e) => setPledgorName(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">Phone</label>
            <input
              type="tel"
              maxLength={50}
              value={pledgorPhone}
              onChange={(e) => setPledgorPhone(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              maxLength={255}
              value={pledgorEmail}
              onChange={(e) => setPledgorEmail(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Amount <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              required
              min="0.001"
              step="0.001"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.000"
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Target Date <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              required
              min={minDate}
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit Pledge"}
          </button>
        </form>
      </div>
    </div>
  );
}
