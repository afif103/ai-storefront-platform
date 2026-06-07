"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/hooks/use-auth";
import { LocaleSwitcher } from "@/components/locale-switcher";

// ---------------------------------------------------------------------------
// Navigation structure (translation keys, resolved at render time)
// ---------------------------------------------------------------------------

interface NavItem {
  labelKey: string;
  href: string;
}

interface NavGroup {
  sectionKey: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    sectionKey: "sectionOverview",
    items: [{ labelKey: "navDashboard", href: "/dashboard" }],
  },
  {
    sectionKey: "sectionAnalytics",
    items: [
      { labelKey: "navAnalytics", href: "/dashboard/analytics" },
      { labelKey: "navReports", href: "/dashboard/reports" },
    ],
  },
  {
    sectionKey: "sectionAI",
    items: [{ labelKey: "navAssistant", href: "/dashboard/assistant" }],
  },
  {
    sectionKey: "sectionStore",
    items: [
      { labelKey: "navStorefront", href: "/dashboard/storefront" },
      { labelKey: "navCategories", href: "/dashboard/categories" },
      { labelKey: "navProducts", href: "/dashboard/products" },
    ],
  },
  {
    sectionKey: "sectionPOS",
    items: [{ labelKey: "navPOS", href: "/dashboard/pos" }],
  },
  {
    sectionKey: "sectionTransactions",
    items: [
      { labelKey: "navOrders", href: "/dashboard/orders" },
      { labelKey: "navCustomers", href: "/dashboard/customers" },
      { labelKey: "navDonations", href: "/dashboard/donations" },
      { labelKey: "navPledges", href: "/dashboard/pledges" },
    ],
  },
  {
    sectionKey: "sectionAdmin",
    items: [{ labelKey: "navManageTenants", href: "/dashboard/admin/tenants" }],
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
  t,
  groups,
}: {
  pathname: string;
  email: string | undefined;
  onLogout: () => void;
  onNavClick?: () => void;
  t: ReturnType<typeof useTranslations>;
  groups: NavGroup[];
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
          {t("title")}
        </Link>
      </div>

      {/* Nav groups */}
      <nav aria-label={t("navLabel")} className="flex-1 overflow-y-auto px-3 py-4">
        {groups.map((group) => (
          <div key={group.sectionKey} className="mb-4">
            <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
              {t(group.sectionKey)}
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
                  {t(item.labelKey)}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Bottom: locale + user + sign out */}
      <div className="border-t px-4 py-3">
        <div className="flex items-center justify-between">
          <p className="truncate text-xs text-gray-500">{email}</p>
          <LocaleSwitcher className="text-xs text-gray-400 hover:text-gray-600" />
        </div>
        <button
          onClick={onLogout}
          className="mt-2 w-full rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
        >
          {t("signOut")}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

const CASHIER_SECTIONS = new Set(["sectionPOS"]);

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, bootstrap, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const t = useTranslations("dashboard");

  const role = bootstrap?.memberships?.[0]?.role;
  const isCashier = role === "cashier";

  useEffect(() => {
    if (isCashier && pathname !== "/dashboard/pos") {
      router.replace("/dashboard/pos");
    }
  }, [isCashier, pathname, router]);

  const navGroups = useMemo(
    () => (isCashier ? NAV_GROUPS.filter((g) => CASHIER_SECTIONS.has(g.sectionKey)) : NAV_GROUPS),
    [isCashier],
  );

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r bg-white lg:block print:hidden">
        <SidebarContent
          pathname={pathname}
          email={user?.email}
          onLogout={handleLogout}
          t={t}
          groups={navGroups}
        />
      </aside>

      {/* Mobile top bar */}
      <div className="sticky top-0 z-20 flex items-center border-b bg-white px-4 py-3 shadow-sm lg:hidden print:hidden">
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
          <span className="sr-only">{t("openMenu")}</span>
        </button>
        <span className="ml-3 text-sm font-semibold text-gray-900">{t("title")}</span>
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
              t={t}
              groups={navGroups}
            />
          </aside>
        </div>
      )}

      {/* Content area */}
      <div className="flex min-h-screen flex-col lg:ml-60 print:ml-0 print:min-h-0">{children}</div>
    </div>
  );
}
