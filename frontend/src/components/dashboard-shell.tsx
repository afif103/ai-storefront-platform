"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

// ---------------------------------------------------------------------------
// Navigation structure
// ---------------------------------------------------------------------------

interface NavItem {
  label: string;
  href: string;
}

interface NavGroup {
  section: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    section: "Overview",
    items: [{ label: "Dashboard", href: "/dashboard" }],
  },
  {
    section: "Analytics",
    items: [{ label: "Analytics", href: "/dashboard/analytics" }],
  },
  {
    section: "AI",
    items: [{ label: "Assistant", href: "/dashboard/assistant" }],
  },
  {
    section: "Store",
    items: [
      { label: "Storefront", href: "/dashboard/storefront" },
      { label: "Categories", href: "/dashboard/categories" },
      { label: "Products", href: "/dashboard/products" },
    ],
  },
  {
    section: "Transactions",
    items: [
      { label: "Orders", href: "/dashboard/orders" },
      { label: "Donations", href: "/dashboard/donations" },
      { label: "Pledges", href: "/dashboard/pledges" },
    ],
  },
  {
    section: "Admin",
    items: [{ label: "Manage Tenants", href: "/dashboard/admin/tenants" }],
  },
];

// ---------------------------------------------------------------------------
// Active state helper
// ---------------------------------------------------------------------------

function isActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname.startsWith(href);
}

// ---------------------------------------------------------------------------
// Sidebar content (shared between desktop and mobile)
// ---------------------------------------------------------------------------

function SidebarContent({
  pathname,
  email,
  onLogout,
  onNavClick,
}: {
  pathname: string;
  email: string | undefined;
  onLogout: () => void;
  onNavClick?: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      {/* Top label */}
      <div className="border-b px-4 py-4">
        <Link
          href="/dashboard"
          className="text-base font-semibold text-gray-900"
          onClick={onNavClick}
        >
          Dashboard
        </Link>
      </div>

      {/* Nav groups */}
      <nav aria-label="Dashboard navigation" className="flex-1 overflow-y-auto px-3 py-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.section} className="mb-4">
            <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
              {group.section}
            </p>
            {group.items.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavClick}
                  className={`block rounded-md px-3 py-2 text-sm ${
                    active
                      ? "bg-blue-50 font-medium text-blue-700"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Bottom: user + sign out */}
      <div className="border-t px-4 py-3">
        <p className="truncate text-xs text-gray-500">{email}</p>
        <button
          onClick={onLogout}
          className="mt-2 w-full rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
        >
          Sign Out
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r bg-white lg:block">
        <SidebarContent
          pathname={pathname}
          email={user?.email}
          onLogout={handleLogout}
        />
      </aside>

      {/* Mobile top bar */}
      <div className="sticky top-0 z-20 flex items-center border-b bg-white px-4 py-3 shadow-sm lg:hidden">
        <button
          onClick={() => setMobileOpen(true)}
          aria-expanded={mobileOpen}
          aria-controls="mobile-sidebar"
          className="rounded p-1.5 text-gray-600 hover:bg-gray-100"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
          <span className="sr-only">Open menu</span>
        </button>
        <span className="ml-3 text-sm font-semibold text-gray-900">Dashboard</span>
      </div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/20"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          {/* Sidebar panel */}
          <aside
            id="mobile-sidebar"
            className="fixed inset-y-0 left-0 z-50 w-60 bg-white shadow-lg"
          >
            <SidebarContent
              pathname={pathname}
              email={user?.email}
              onLogout={handleLogout}
              onNavClick={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      )}

      {/* Content area */}
      <div className="flex min-h-screen flex-col lg:ml-60">{children}</div>
    </div>
  );
}
