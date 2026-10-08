"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { Logo } from "@/components/ui/logo";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { cn } from "@/lib/utils";

const links = [
  { href: "#how", label: "How it works" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "#agents", label: "Agents" },
  { href: "#reliability", label: "Reliability" },
  { href: "/app/docs", label: "API" },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 12);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  return (
    <header className={cn("fixed inset-x-0 top-0 z-50 transition-all duration-300", scrolled ? "py-2" : "py-4")}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <nav
          className={cn(
            "flex items-center justify-between rounded-full px-4 py-2 transition-all duration-300",
            scrolled ? "bg-surface/80 border border-line shadow-md backdrop-blur-xl" : "bg-transparent border border-transparent",
          )}
        >
          <Logo />
          <div className="hidden items-center gap-1 md:flex">
            {links.map((l) => (
              <Link key={l.href} href={l.href} className="rounded-full px-3.5 py-1.5 text-[13.5px] text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink">
                {l.label}
              </Link>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button href="/app" size="sm" variant="dark" className="hidden sm:inline-flex">
              Open workspace <ArrowUpRight size={14} />
            </Button>
            <button className="inline-flex h-9 w-9 items-center justify-center rounded-full text-ink-2 md:hidden" onClick={() => setOpen((v) => !v)} aria-label="Menu">
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </nav>
        {open && (
          <div className="mt-2 rounded-2xl border border-line bg-surface p-3 shadow-md md:hidden">
            {links.map((l) => (
              <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-surface-2">
                {l.label}
              </Link>
            ))}
            <Button href="/app" size="sm" variant="dark" className="mt-2 w-full">Open workspace</Button>
          </div>
        )}
      </div>
    </header>
  );
}
