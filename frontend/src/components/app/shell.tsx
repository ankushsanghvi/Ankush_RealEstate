"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, GitCompareArrows, Table2, FlaskConical, BookOpen, ArrowLeft, PanelLeftClose, PanelLeftOpen, Circle } from "lucide-react";
import { Logo, LogoMark } from "@/components/ui/logo";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { healthcheck } from "@/lib/api";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/app", label: "Valuation console", icon: Compass },
  { href: "/app/compare", label: "Compare properties", icon: GitCompareArrows },
  { href: "/app/properties", label: "Property records", icon: Table2 },
  { href: "/app/evaluation", label: "Evaluation & feedback", icon: FlaskConical },
  { href: "/app/docs", label: "API reference", icon: BookOpen },
];

export function Shell({ children, title, subtitle }: { children: React.ReactNode; title: string; subtitle?: string }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [health, setHealth] = useState<{ ok: boolean; mode: "live" | "demo"; latencyMs: number; engine?: string; records?: number; llmError?: string | null; llmModel?: string | null } | null>(null);

  useEffect(() => {
    let alive = true;
    healthcheck().then((h) => alive && setHealth(h));
    const id = setInterval(() => healthcheck().then((h) => alive && setHealth(h)), 30000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <div className="flex min-h-screen bg-paper">
      {/* Sidebar */}
      <aside className={cn("sticky top-0 hidden h-screen shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-300 md:flex", collapsed ? "w-[68px]" : "w-[248px]")}>
        <div className={cn("flex h-16 items-center border-b border-line", collapsed ? "justify-center" : "justify-between px-5")}>
          {collapsed ? <Link href="/"><LogoMark /></Link> : <Logo />}
          {!collapsed && (
            <button onClick={() => setCollapsed(true)} className="text-ink-3 hover:text-ink" aria-label="Collapse sidebar"><PanelLeftClose size={16} /></button>
          )}
        </div>
        {collapsed && (
          <button onClick={() => setCollapsed(false)} className="mx-auto mt-3 text-ink-3 hover:text-ink" aria-label="Expand sidebar"><PanelLeftOpen size={16} /></button>
        )}
        <nav className="flex-1 space-y-1 p-3">
          {nav.map((n) => {
            const active = pathname === n.href;
            return (
              <Link
                key={n.href}
                href={n.href}
                title={n.label}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] transition-colors",
                  active ? "bg-accent-soft text-accent-ink font-medium" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                  collapsed && "justify-center px-0",
                )}
              >
                <n.icon size={17} className="shrink-0" />
                {!collapsed && <span className="truncate">{n.label}</span>}
              </Link>
            );
          })}
        </nav>
        <div className={cn("border-t border-line p-3", collapsed && "flex justify-center")}>
          {collapsed ? (
            <Circle size={10} className={cn(health?.mode === "live" ? "fill-good text-good" : "fill-sun text-sun")} />
          ) : (
            <div className="rounded-xl bg-surface-2 p-3 text-[12px]">
              <div className="flex items-center justify-between">
                <span className="text-ink-3">Backend</span>
                {health === null ? (
                  <Badge tone="outline">checking…</Badge>
                ) : health.mode === "live" ? (
                  <Badge tone="good"><span className="h-1.5 w-1.5 rounded-full bg-good" /> live · {health.latencyMs}ms</Badge>
                ) : (
                  <Badge tone="warning"><span className="h-1.5 w-1.5 rounded-full bg-sun" /> demo mode</Badge>
                )}
              </div>
              {health?.mode === "demo" && <p className="mt-2 leading-snug text-ink-3">No API reachable. Showing deterministic demo data so the UI stays usable.</p>}
              {health?.mode === "live" && <p className="mt-2 leading-snug text-ink-3">{health.records?.toLocaleString()} records indexed · {health.engine === "llm" ? `LLM agents (${health.llmModel})` : "rules engine (no LLM key)"}</p>}
              {health?.llmError && <p className="mt-1.5 rounded-md bg-[rgba(236,131,90,0.12)] px-2 py-1 leading-snug text-[11.5px] text-[color:var(--status-serious)]">LLM degraded → rules: {health.llmError}</p>}
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-line bg-paper/80 px-4 backdrop-blur-xl sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Link href="/" className="inline-flex h-8 w-8 items-center justify-center rounded-full text-ink-3 hover:bg-surface-2 hover:text-ink md:hidden" aria-label="Home"><ArrowLeft size={16} /></Link>
            <div className="min-w-0">
              <h1 className="truncate text-[15px] font-semibold tracking-tight text-ink">{title}</h1>
              {subtitle && <p className="truncate text-[12px] text-ink-3">{subtitle}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {health?.mode === "demo" && <Badge tone="warning" className="hidden sm:inline-flex">Demo data</Badge>}
            <ThemeToggle />
          </div>
        </header>
        {/* mobile nav */}
        <div className="flex gap-1 overflow-x-auto border-b border-line bg-surface px-3 py-2 md:hidden">
          {nav.map((n) => (
            <Link key={n.href} href={n.href} className={cn("whitespace-nowrap rounded-full px-3 py-1.5 text-[12.5px]", pathname === n.href ? "bg-accent-soft text-accent-ink" : "text-ink-2")}>{n.label}</Link>
          ))}
        </div>
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
