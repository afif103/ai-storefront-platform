"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { apiFetch } from "@/lib/api-client";

interface Category {
  id: string;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
  created_at: string;
}

interface PaginatedCategories {
  items: Category[];
  next_cursor: string | null;
  has_more: boolean;
}

function CategoriesContent() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState("");
  const searchParams = useSearchParams();

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    const result = await apiFetch<PaginatedCategories>(
      "/api/v1/tenants/me/categories",
    );
    if (result.ok) {
      setCategories(result.data.items);
    } else {
      setError(result.detail);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await fetchCategories();
      if (cancelled) return;
    })();
    return () => { cancelled = true; };
  }, [searchParams, fetchCategories]);

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete "${name}"?`)) return;
    setDeletingIds((prev) => new Set(prev).add(id));
    setError("");

    const result = await apiFetch(`/api/v1/tenants/me/categories/${id}`, {
      method: "DELETE",
    });

    setDeletingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });

    if (result.ok) {
      setCategories((prev) => prev.filter((c) => c.id !== id));
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      showToast(`Deleted "${name}"`);
    } else {
      setError(`Failed to delete "${name}": ${result.detail}`);
    }
  }

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    const count = selected.size;
    if (!confirm(`Delete ${count} category(ies)?`)) return;

    const ids = [...selected];
    setDeletingIds(new Set(ids));
    setError("");

    const result = await apiFetch<{ deleted: number }>(
      "/api/v1/tenants/me/categories/bulk-delete",
      {
        method: "POST",
        body: JSON.stringify({ ids }),
      },
    );

    setDeletingIds(new Set());

    if (result.ok) {
      const deletedSet = new Set(ids);
      setCategories((prev) => prev.filter((c) => !deletedSet.has(c.id)));
      setSelected(new Set());
      showToast(`Deleted ${result.data.deleted} category(ies)`);
    } else {
      setError(`Bulk delete failed: ${result.detail}`);
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === categories.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(categories.map((c) => c.id)));
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="text-sm text-blue-600 hover:underline"
            >
              Dashboard
            </Link>
            <span className="text-gray-300">/</span>
            <h1 className="text-lg font-semibold text-gray-900">Categories</h1>
          </div>
          <div className="flex items-center gap-2">
            {selected.size > 0 && (
              <button
                onClick={handleBulkDelete}
                disabled={deletingIds.size > 0}
                className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                Delete {selected.size} selected
              </button>
            )}
            <Link
              href="/dashboard/categories/new"
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Add Category
            </Link>
          </div>
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
        ) : categories.length === 0 ? (
          <div className="rounded-lg border bg-white p-8 text-center">
            <p className="text-gray-500">No categories yet.</p>
            <Link
              href="/dashboard/categories/new"
              className="mt-2 inline-block text-sm text-blue-600 hover:underline"
            >
              Create your first category
            </Link>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3 w-8">
                    <input
                      type="checkbox"
                      checked={selected.size === categories.length && categories.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded"
                    />
                  </th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Sort Order</th>
                  <th className="px-4 py-3">Active</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {categories.map((cat) => {
                  const isDeleting = deletingIds.has(cat.id);
                  return (
                    <tr key={cat.id} className={isDeleting ? "opacity-50" : ""}>
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selected.has(cat.id)}
                          onChange={() => toggleSelect(cat.id)}
                          disabled={isDeleting}
                          className="rounded"
                        />
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {cat.name}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {cat.sort_order}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                            cat.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {cat.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {new Date(cat.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <Link
                            href={`/dashboard/categories/${cat.id}/edit`}
                            className="text-blue-600 hover:underline"
                          >
                            Edit
                          </Link>
                          <button
                            onClick={() => handleDelete(cat.id, cat.name)}
                            disabled={isDeleting}
                            className="text-red-600 hover:underline disabled:opacity-50"
                          >
                            {isDeleting ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {toast && (
        <div className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-gray-900 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}

export default function CategoriesPage() {
  return (
    <RequireAuth>
      <CategoriesContent />
    </RequireAuth>
  );
}
