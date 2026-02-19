"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
import { apiFetch } from "@/lib/api-client";

interface Product {
  id: string;
  category_id: string | null;
  name: string;
  description: string | null;
  price_amount: string;
  currency: string | null;
  effective_currency: string;
  is_active: boolean;
  sort_order: number;
}

interface PaginatedProducts {
  items: Product[];
  next_cursor: string | null;
  has_more: boolean;
}

function ProductsContent() {
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchProducts() {
      setLoading(true);
      const result = await apiFetch<PaginatedProducts>(
        "/api/v1/tenants/me/products"
      );
      if (result.ok) {
        setProducts(result.data.items);
      } else {
        setError(result.detail);
      }
      setLoading(false);
    }
    fetchProducts();
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Delete this product?")) return;
    const result = await apiFetch(`/api/v1/tenants/me/products/${id}`, {
      method: "DELETE",
    });
    if (result.ok) {
      setProducts((prev) => prev.filter((p) => p.id !== id));
    } else {
      setError(result.detail);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">
              Dashboard
            </Link>
            <span className="text-gray-300">/</span>
            <h1 className="text-lg font-semibold text-gray-900">Products</h1>
          </div>
          <Link
            href="/dashboard/products/new"
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Add Product
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : products.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">No products yet.</p>
            <Link
              href="/dashboard/products/new"
              className="mt-2 inline-block text-sm text-blue-600 hover:underline"
            >
              Create your first product
            </Link>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Active</th>
                  <th className="px-4 py-3">Sort</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {products.map((prod) => (
                  <tr key={prod.id}>
                    <td className="px-4 py-3 font-medium text-gray-900">
                      {prod.name}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {prod.price_amount} {prod.effective_currency}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          prod.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {prod.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{prod.sort_order}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <Link
                          href={`/dashboard/products/${prod.id}/edit`}
                          className="text-blue-600 hover:underline"
                        >
                          Edit
                        </Link>
                        <button
                          onClick={() => handleDelete(prod.id)}
                          className="text-red-600 hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

export default function ProductsPage() {
  return (
    <RequireAuth>
      <ProductsContent />
    </RequireAuth>
  );
}
