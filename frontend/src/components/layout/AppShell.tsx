"use client";

import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { ToastProvider } from "@/components/ui/Toast";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <div className="mx-auto flex min-h-screen max-w-[1440px]">
        <Sidebar />
        <main className="min-w-0 flex-1 px-4 pb-10 pt-16 md:px-8 md:pt-8">{children}</main>
      </div>
    </ToastProvider>
  );
}
