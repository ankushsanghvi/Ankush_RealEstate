import { Navbar } from "@/components/marketing/navbar";
import { Hero } from "@/components/marketing/hero";
import { Marquee } from "@/components/marketing/marquee";
import { Pipeline } from "@/components/marketing/pipeline";
import { Features } from "@/components/marketing/features";
import { Agents } from "@/components/marketing/agents";
import { Reliability } from "@/components/marketing/reliability";
import { CTA, Footer } from "@/components/marketing/cta-footer";

export default function Home() {
  return (
    <main className="flex-1">
      <Navbar />
      <Hero />
      <Marquee />
      <Pipeline />
      <Features />
      <Agents />
      <Reliability />
      <CTA />
      <Footer />
    </main>
  );
}
