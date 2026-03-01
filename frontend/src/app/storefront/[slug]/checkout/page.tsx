"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api-client";
import { useVisit } from "@/hooks/use-visit";
import { useCart } from "@/hooks/use-cart";

interface OrderResponse {
  id: string;
  order_number: string;
  total_amount: string;
  currency: string;
  status: string;
  created_at: string;
}

export default function CheckoutPage() {
  const params = useParams();
  const slug = params.slug as string;
  const { visitId } = useVisit(slug);
  const cart = useCart(slug);

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [paymentNotes, setPaymentNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<OrderResponse | null>(null);

  const cartTotal = cart.items
    .reduce((sum, i) => sum + parseFloat(i.priceAmount) * i.qty, 0)
    .toFixed(3);
  const cartCurrency = cart.items[0]?.currency ?? "KWD";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    const result = await apiFetch<OrderResponse>(
      `/api/v1/storefront/${slug}/orders`,
      {
        method: "POST",
        body: JSON.stringify({
          customer_name: customerName,
          customer_phone: customerPhone || undefined,
          customer_email: customerEmail || undefined,
          items: cart.items.map((i) => ({
            catalog_item_id: i.catalogItemId,
            qty: i.qty,
          })),
          payment_notes: paymentNotes || undefined,
          visit_id: visitId || undefined,
        }),
      }
    );

    setSubmitting(false);
    if (result.ok) {
      setSuccess(result.data);
      cart.clearCart();
    } else {
      setError(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail));
    }
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-md rounded-lg border border-green-300 bg-green-50 p-8 text-center">
          <h2 className="text-lg font-bold text-green-800">Order Placed!</h2>
          <p className="mt-2 text-sm text-green-700">
            Order number: <span className="font-mono font-bold">{success.order_number}</span>
          </p>
          <p className="mt-1 text-sm text-green-700">
            Total: {success.total_amount} {success.currency}
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

  if (cart.items.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-md rounded-lg border bg-white p-8 text-center">
          <p className="text-gray-500">Your cart is empty.</p>
          <Link
            href={`/storefront/${slug}`}
            className="mt-4 inline-block rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Browse Products
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

        <h1 className="mb-6 text-2xl font-bold text-gray-900">Checkout</h1>

        {/* Cart summary */}
        <div className="mb-6 rounded-lg border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Your Items</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2">Item</th>
                <th className="pb-2 text-center">Qty</th>
                <th className="pb-2 text-right">Subtotal</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {cart.items.map((item) => (
                <tr key={item.catalogItemId} className="border-b last:border-0">
                  <td className="py-2 text-gray-900">{item.name}</td>
                  <td className="py-2 text-center">
                    <div className="inline-flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          if (item.qty <= 1) {
                            cart.removeItem(item.catalogItemId);
                          } else {
                            cart.addItem(
                              {
                                catalogItemId: item.catalogItemId,
                                name: item.name,
                                priceAmount: item.priceAmount,
                                currency: item.currency,
                              },
                              -1
                            );
                          }
                        }}
                        className="rounded border px-1.5 text-gray-500 hover:bg-gray-100"
                      >
                        -
                      </button>
                      <span className="w-6 text-center">{item.qty}</span>
                      <button
                        type="button"
                        onClick={() =>
                          cart.addItem(
                            {
                              catalogItemId: item.catalogItemId,
                              name: item.name,
                              priceAmount: item.priceAmount,
                              currency: item.currency,
                            },
                            1
                          )
                        }
                        className="rounded border px-1.5 text-gray-500 hover:bg-gray-100"
                      >
                        +
                      </button>
                    </div>
                  </td>
                  <td className="py-2 text-right text-gray-900">
                    {(parseFloat(item.priceAmount) * item.qty).toFixed(3)} {item.currency}
                  </td>
                  <td className="py-2 pl-2 text-right">
                    <button
                      type="button"
                      onClick={() => cart.removeItem(item.catalogItemId)}
                      className="text-red-500 hover:text-red-700"
                      title="Remove"
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex justify-between border-t pt-3 font-bold text-gray-900">
            <span>Total</span>
            <span>
              {cartTotal} {cartCurrency}
            </span>
          </div>
        </div>

        {/* Order form */}
        <form onSubmit={handleSubmit} className="rounded-lg border bg-white p-4">
          <h2 className="mb-4 text-sm font-semibold text-gray-700">Your Details</h2>

          {error && (
            <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              maxLength={255}
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">Phone</label>
            <input
              type="tel"
              maxLength={50}
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              maxLength={255}
              value={customerEmail}
              onChange={(e) => setCustomerEmail(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-gray-700">Payment Notes</label>
            <textarea
              maxLength={2000}
              value={paymentNotes}
              onChange={(e) => setPaymentNotes(e.target.value)}
              rows={2}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Placing Order..." : "Place Order"}
          </button>
        </form>
      </div>
    </div>
  );
}
