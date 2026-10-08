import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { Reveal } from "@/components/ui/reveal";

export function CTA() {
  return (
    <section className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <div className="relative overflow-hidden rounded-[28px] bg-paper-2 px-6 py-16 text-center sm:px-12 sm:py-24">
            <div className="relative">
              <h2 className="display mx-auto max-w-3xl text-[36px] sm:text-[56px] text-ink">
                Ask the question a valuer would ask. <em>Get the answer</em> a reviewer would accept.
              </h2>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Button href="/app" size="lg">Open the workspace <ArrowRight size={16} /></Button>
                <Button href="/app/docs" size="lg" variant="outline">Read the API docs</Button>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line py-10">
      <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-4 sm:flex-row sm:items-center sm:px-6">
        <div>
          <Logo />
          <p className="mt-2 text-[12.5px] text-ink-3">AI-powered real estate valuation assistant · Ames Housing dataset</p>
        </div>
        <div className="flex gap-6 text-[13px] text-ink-2">
          <a href="/app" className="hover:text-ink">Workspace</a>
          <a href="/app/docs" className="hover:text-ink">API</a>
          <a href="/app/evaluation" className="hover:text-ink">Evaluation</a>
          <a href="https://www.openml.org/search?type=data&sort=runs&id=43926" target="_blank" rel="noreferrer" className="hover:text-ink">Dataset ↗</a>
        </div>
      </div>
    </footer>
  );
}
