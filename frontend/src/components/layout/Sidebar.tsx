"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Brain,
  ClipboardCheck,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { AxiomMark } from "@/components/brand/AxiomMark";

const STORAGE_KEY = "axiom-sidebar-collapsed";

const nav = [
  { href: "/", label: "總覽", icon: LayoutDashboard },
  { href: "/materials", label: "教材", icon: BookOpen },
  { href: "/tutor", label: "教學", icon: Sparkles },
  { href: "/solver", label: "解題", icon: Brain },
  { href: "/progress", label: "進度", icon: TrendingUp },
  { href: "/evaluation", label: "試驗", icon: ClipboardCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      // ignore
    }
    setReady(true);
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        // ignore
      }
      return next;
    });
  }

  const navLinks = (opts?: { onNavigate?: () => void; compact?: boolean }) =>
    nav.map((item) => {
      const active = pathname === item.href;
      const Icon = item.icon;
      const compact = opts?.compact;
      return (
        <Link
          key={item.href}
          href={item.href}
          title={item.label}
          onClick={opts?.onNavigate}
          className={cn(
            "flex items-center rounded-xl text-sm transition",
            compact ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
            active
              ? "bg-ink-950 text-white shadow-soft"
              : "text-ink-600 hover:bg-white/70 hover:text-ink-950"
          )}
        >
          <Icon className="h-4 w-4 shrink-0" />
          {!compact ? <span>{item.label}</span> : null}
        </Link>
      );
    });

  return (
    <>
      <button
        type="button"
        className="fixed left-4 top-4 z-50 flex h-11 w-11 items-center justify-center rounded-xl border border-ink-100 bg-white/90 shadow-soft backdrop-blur md:hidden"
        onClick={() => setMobileOpen(true)}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <aside
        className={cn(
          "hidden shrink-0 flex-col border-r border-ink-100/80 bg-white/50 backdrop-blur-xl transition-[width] duration-200 ease-out md:flex",
          ready ? (collapsed ? "w-[4.75rem]" : "w-64") : "w-64",
          collapsed ? "p-3" : "p-5"
        )}
      >
        <div className="mb-6 flex items-center gap-2">
          <Link
            href="/"
            title="Axiom"
            className={cn(
              "group flex min-w-0 items-center gap-3",
              collapsed && "mx-auto"
            )}
          >
            <AxiomMark size={40} />
            {!collapsed ? (
              <div className="min-w-0">
                <div className="font-display text-lg tracking-tight text-ink-950">
                  Axiom
                </div>
              </div>
            ) : null}
          </Link>
        </div>

        <nav className={cn("flex flex-1 flex-col gap-1", collapsed && "items-stretch")}>
          {navLinks({ compact: collapsed })}
        </nav>

        <button
          type="button"
          onClick={toggleCollapsed}
          className={cn(
            "mt-4 flex items-center rounded-xl border border-ink-100 bg-white/70 text-ink-600 transition hover:bg-white hover:text-ink-950",
            collapsed ? "justify-center px-0 py-2.5" : "gap-2 px-3 py-2 text-xs"
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "展開側欄" : "收合側欄"}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink-950/35"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu overlay"
          />
          <div className="absolute inset-y-0 left-0 flex w-[80%] max-w-xs flex-col animate-fadeUp bg-[#f7f8fa] p-5 shadow-panel">
            <button
              type="button"
              className="mb-4 ml-auto flex h-9 w-9 items-center justify-center rounded-lg border border-ink-100 bg-white"
              onClick={() => setMobileOpen(false)}
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="mb-8 px-1">
              <Link
                href="/"
                className="group flex items-center gap-3"
                onClick={() => setMobileOpen(false)}
              >
                <AxiomMark size={40} />
                <div>
                  <div className="font-display text-lg tracking-tight text-ink-950">
                    Axiom
                  </div>
                </div>
              </Link>
            </div>
            <nav className="flex flex-1 flex-col gap-1">
              {navLinks({ onNavigate: () => setMobileOpen(false) })}
            </nav>
          </div>
        </div>
      ) : null}
    </>
  );
}
