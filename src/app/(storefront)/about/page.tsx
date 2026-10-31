import Image from "next/image";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function AboutPage() {
  return (
    <div className="bg-cream">
      <div className="border-b border-sand/50 bg-warm-cream"><div className="container-page py-16 text-center md:py-20"><p className="label-text mb-3 text-terracotta">The brand</p><h1 className="heading-xl mx-auto mb-4 max-w-2xl text-charcoal">Modest Chic by Hira &amp; Muqadas</h1><p className="body-lg mx-auto max-w-xl text-charcoal/75">A considered space for modest style, warm colour, and everyday elegance.</p></div></div>
      <div className="container-page grid items-center gap-12 py-16 md:grid-cols-2 md:gap-20 md:py-24">
        <div className="relative mx-auto aspect-[4/5] w-full max-w-md overflow-hidden rounded-[44%_44%_24px_24px] bg-[#ede2dc]"><Image src="/images/modest-chic-official-logo.jpeg" alt="Modest Chic by Hira and Muqadas logo" fill sizes="(max-width: 768px) 85vw, 40vw" className="object-contain" /></div>
        <div className="max-w-lg"><p className="label-text mb-3 text-terracotta">Our visual language</p><h2 className="heading-lg mb-5 text-charcoal">Softness with intention.</h2><p className="body-base mb-4 text-charcoal/75">The Modest Chic mark brings together a graceful profile, botanical lines, and a warm neutral palette. Those details guide the calm, expressive feel of this storefront.</p><p className="body-base mb-8 text-charcoal/75">Find the latest product details and available shades in the collection.</p><Link href="/shop" className="inline-flex items-center gap-2 rounded-full bg-charcoal px-6 py-3 text-sm font-medium text-cream hover:bg-deep-rust">Explore the collection <ArrowRight className="h-4 w-4" /></Link></div>
      </div>
    </div>
  );
}
