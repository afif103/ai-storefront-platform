"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import { useVisit } from "@/hooks/use-visit";

interface DonationResponse {
  id: string;
  donation_number: string;
  amount: string;
  currency: string;
  status: string;
  created_at: string;
}

export default function DonatePage() {
  const params = useParams();
  const slug = params.slug as string;
  const { visitId } = useVisit(slug);

  const [donorName, setDonorName] = useState("");
  const [donorPhone, setDonorPhone] = useState("");
  const [donorEmail, setDonorEmail] = useState("");
  const [amount, setAmount] = useState("");
  const [campaign, setCampaign] = useState("");
  const [receiptRequested, setReceiptRequested] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<DonationResponse | null>(null);

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

    setSubmitting(true);

    const result = await apiFetch<DonationResponse>(
      `/api/v1/storefront/${slug}/donations`,
      {
        method: "POST",
        body: JSON.stringify({
          donor_name: donorName,
          donor_phone: donorPhone || undefined,
          donor_email: donorEmail || undefined,
          amount: formatted,
          campaign: campaign || undefined,
          receipt_requested: receiptRequested,
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
          <h2 className="text-lg font-bold text-green-800">Thank You!</h2>
          <p className="mt-2 text-sm text-green-700">
            Donation number: <span className="font-mono font-bold">{success.donation_number}</span>
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

        <h1 className="mb-6 text-2xl font-bold text-gray-900">Make a Donation</h1>

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
              value={donorName}
              onChange={(e) => setDonorName(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">Phone</label>
            <input
              type="tel"
              maxLength={50}
              value={donorPhone}
              onChange={(e) => setDonorPhone(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              maxLength={255}
              value={donorEmail}
              onChange={(e) => setDonorEmail(e.target.value)}
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
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">Campaign</label>
            <input
              type="text"
              maxLength={255}
              value={campaign}
              onChange={(e) => setCampaign(e.target.value)}
              placeholder="e.g. Ramadan 2026"
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-4 flex items-center gap-2">
            <input
              type="checkbox"
              id="receipt"
              checked={receiptRequested}
              onChange={(e) => setReceiptRequested(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            <label htmlFor="receipt" className="text-sm text-gray-700">
              I would like a receipt
            </label>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit Donation"}
          </button>
        </form>
      </div>
    </div>
  );
}
