"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api-client";
import { initAnalytics, track, flush, getOrCreateSessionId } from "@/lib/analytics";
import { useVisit } from "@/hooks/use-visit";
import { useCart } from "@/hooks/use-cart";

interface OrderItem {
  name: string;
  qty: number;
  unit_price: string;
  currency: string;
  subtotal: string;
}

interface OrderResponse {
  id: string;
  order_number: string;
  customer_name: string;
  items: OrderItem[];
  total_amount: string;
  currency: string;
  status: string;
  payment_method: string | null;
  created_at: string;
}

interface PublicConfig {
  payment_methods: string[] | null;
}

export default function CheckoutPage() {
  const params = useParams();
  const slug = params.slug as string;
  const t = useTranslations("checkout");
  const tPayment = useTranslations("paymentMethods");
  const paymentMethodLabels: Record<string, string> = {
    cash: tPayment("cash"),
    knet: tPayment("knet"),
    bank_transfer: tPayment("bank_transfer"),
    cod: tPayment("cod"),
    manual: tPayment("manual"),
  };
  const { visitId } = useVisit(slug);
  const cart = useCart(slug);

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [paymentNotes, setPaymentNotes] = useState("");
  const [onlineMethods, setOnlineMethods] = useState<string[]>([]);
  const [paymentMethod, setPaymentMethod] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<OrderResponse | null>(null);

  const cartTotal = cart.items
    .reduce((sum, i) => sum + parseFloat(i.priceAmount) * i.qty, 0)
    .toFixed(3);
  const cartCurrency = cart.items[0]?.currency ?? "KWD";

  // Analytics: begin_checkout on mount (guarded to prevent StrictMode double-fire)
  useEffect(() => {
    initAnalytics(slug);
    if (cart.items.length > 0) {
      const key = `analytics_begin_checkout_fired:${slug}:${getOrCreateSessionId()}`;
      if (!localStorage.getItem(key)) {
        track("begin_checkout", { cart_value: cartTotal });
        localStorage.setItem(key, "1");
      }
    }
    return () => flush();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await apiFetch<PublicConfig>(
        `/api/v1/storefront/${slug}/config`
      );
      if (cancelled) return;
      if (
        result.ok &&
        result.data.payment_methods &&
        result.data.payment_methods.length > 0
      ) {
        setOnlineMethods(result.data.payment_methods);
        setPaymentMethod(result.data.payment_methods[0]);
      }
    })();
    return () => { cancelled = true; };
  }, [slug]);

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
          payment_method: paymentMethod || undefined,
          visit_id: visitId || undefined,
        }),
      }
    );

    setSubmitting(false);
    if (result.ok) {
      track("submit_order", {
        order_number: result.data.order_number,
        value: result.data.total_amount,
      });
      flush();
      setSuccess(result.data);
      cart.clearCart();
    } else {
      setError(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail));
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 px-4 py-8">
        <div className="mx-auto max-w-md">
          <div className="rounded-lg border bg-white p-6 shadow-sm">
            <h2 className="text-center text-xl font-bold text-green-700">
              {t("orderPlaced")}
            </h2>
            <p className="mt-1 text-center text-sm font-medium text-gray-900">
              {t("orderNumber")}{" "}
              <span className="font-mono">{success.order_number}</span>
            </p>
            <p className="mt-1 text-center text-xs text-gray-500">
              {new Date(success.created_at).toLocaleString()}
            </p>
            <p className="mt-1 text-center text-sm text-gray-700">
              {t("receiptCustomer")} {success.customer_name}
            </p>

            {success.items.length > 0 && (
              <table className="mt-4 w-full text-sm">
                <thead className="border-b text-left text-xs font-medium uppercase text-gray-500">
                  <tr>
                    <th className="py-1">{t("item")}</th>
                    <th className="py-1 text-center">{t("qty")}</th>
                    <th className="py-1 text-right">{t("unitPrice")}</th>
                    <th className="py-1 text-right">{t("subtotal")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {success.items.map((lineItem, i) => (
                    <tr key={i}>
                      <td className="py-1 text-gray-900">{lineItem.name}</td>
                      <td className="py-1 text-center text-gray-700">
                        {lineItem.qty}
                      </td>
                      <td className="py-1 text-right text-gray-700">
                        {lineItem.unit_price}
                      </td>
                      <td className="py-1 text-right text-gray-700">
                        {lineItem.subtotal}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div className="mt-3 border-t pt-2 text-right text-sm font-semibold text-gray-900">
              {t("totalConfirm")} {success.total_amount} {success.currency}
            </div>

            {success.payment_method && (
              <div className="mt-1 text-right text-sm text-gray-700">
                {tPayment("fieldLabel")}:{" "}
                {paymentMethodLabels[success.payment_method] ??
                  success.payment_method}
              </div>
            )}
          </div>

          <div className="mt-4 flex gap-3 print:hidden">
            <button
              type="button"
              onClick={() => window.print()}
              className="flex-1 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              {t("printReceipt")}
            </button>
            <Link
              href={`/storefront/${slug}`}
              className="flex-1 rounded-lg bg-green-700 px-4 py-2 text-center text-sm font-medium text-white hover:bg-green-800"
            >
              {t("backToStore")}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (cart.items.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-md rounded-lg border bg-white p-8 text-center">
          <p className="text-gray-500">{t("emptyCart")}</p>
          <Link
            href={`/storefront/${slug}`}
            className="mt-4 inline-block rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("browseProducts")}
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
          {t("backLink")}
        </Link>

        <h1 className="mb-6 text-2xl font-bold text-gray-900">{t("title")}</h1>

        {/* Cart summary */}
        <div className="mb-6 rounded-lg border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">{t("yourItems")}</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-start text-gray-500">
                <th className="pb-2">{t("item")}</th>
                <th className="pb-2 text-center">{t("qty")}</th>
                <th className="pb-2 text-end">{t("subtotal")}</th>
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
                  <td className="py-2 text-end text-gray-900">
                    {(parseFloat(item.priceAmount) * item.qty).toFixed(3)} {item.currency}
                  </td>
                  <td className="py-2 ps-2 text-end">
                    <button
                      type="button"
                      onClick={() => cart.removeItem(item.catalogItemId)}
                      className="text-red-500 hover:text-red-700"
                      title={t("remove")}
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex justify-between border-t pt-3 font-bold text-gray-900">
            <span>{t("total")}</span>
            <span>
              {cartTotal} {cartCurrency}
            </span>
          </div>
        </div>

        {/* Order form */}
        <form onSubmit={handleSubmit} className="rounded-lg border bg-white p-4">
          <h2 className="mb-4 text-sm font-semibold text-gray-700">{t("yourDetails")}</h2>

          {error && (
            <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              {t("name")} <span className="text-red-500">*</span>
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
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("phone")}</label>
            <input
              type="tel"
              maxLength={50}
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("email")}</label>
            <input
              type="email"
              maxLength={255}
              value={customerEmail}
              onChange={(e) => setCustomerEmail(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("paymentNotes")}</label>
            <textarea
              maxLength={2000}
              value={paymentNotes}
              onChange={(e) => setPaymentNotes(e.target.value)}
              rows={2}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>

          {onlineMethods.length > 0 && (
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {tPayment("fieldLabel")}
              </label>
              <select
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              >
                {onlineMethods.map((code) => (
                  <option key={code} value={code}>
                    {paymentMethodLabels[code] ?? code}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? t("placingOrder") : t("placeOrder")}
          </button>
        </form>
      </div>
    </div>
  );
}
