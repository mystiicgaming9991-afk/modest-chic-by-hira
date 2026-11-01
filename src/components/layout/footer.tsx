"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Camera, Mail } from "lucide-react";
import { getContactChannels } from "@/lib/contact";

const footerLinks = {
  shop: {
    title: "Shop",
    links: [
      { label: "All Hijabs", href: "/shop" },
      { label: "New Arrivals", href: "/collections/new-arrivals" },
      { label: "Featured Pieces", href: "/collections/best-sellers" },
      { label: "Accessories", href: "/shop?category=accessories" },
      { label: "Gift Sets", href: "/shop?category=sets" },
    ],
  },
  support: {
    title: "Help",
    links: [
      { label: "Contact Us", href: "/contact" },
      { label: "Privacy", href: "/privacy" },
      { label: "FAQ", href: "/faq" },
      { label: "Shipping Policy", href: "/shipping" },
      { label: "Returns & Exchanges", href: "/returns" },
    ],
  },
  company: {
    title: "Modest Chic by Hira & Muqadas",
    links: [
      { label: "About Us", href: "/about" },
    ],
  },
};

export function Footer() {
  const { email, instagram } = getContactChannels();
  const [year, setYear] = useState<number | null>(null);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setYear(new Date().getFullYear());
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, []);

  return (
    <footer id="site-footer" className="bg-charcoal text-cream/80">
      {/* Main Footer */}
      <div className="container-page py-16 md:py-20">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10 md:gap-16">
          {/* Brand Column */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="inline-block mb-4">
              <span className="flex items-center gap-3">
                <span className="relative h-12 w-12 shrink-0 overflow-hidden rounded-full border border-cream/20 bg-[#eee8e3]">
                  <Image src="/images/modest-chic-official-logo.jpeg" alt="" fill sizes="48px" className="object-cover object-[center_16%]" />
                </span>
                <span className="flex flex-col">
                  <span className="font-display text-lg uppercase tracking-[0.15em] text-cream">Modest Chic</span>
                  <span className="text-[9px] uppercase tracking-[0.18em] text-cream/65">by Hira &amp; Muqadas</span>
                </span>
              </span>
            </Link>
            <p className="body-sm text-cream/60 mb-6 max-w-xs leading-relaxed">
              A warm, considered edit of hijabs and modest style by Hira &amp; Muqadas.
            </p>
            {(email || instagram) && (
              <ul aria-label="Contact channels" className="space-y-3 text-sm">
                {email && <li><a href={email.href} className="inline-flex max-w-full items-start gap-2 rounded text-cream/80 hover:text-cream focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cream"><Mail aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /><span className="min-w-0 break-all"><span className="sr-only">Email: </span>{email.label}</span></a></li>}
                {instagram && <li><a href={instagram.href} target="_blank" rel="noopener noreferrer" className="inline-flex max-w-full items-start gap-2 rounded text-cream/80 hover:text-cream focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cream"><Camera aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /><span className="min-w-0 break-all"><span className="sr-only">Instagram: </span>{instagram.label}<span className="sr-only"> (opens in a new tab)</span></span></a></li>}
              </ul>
            )}
          </div>

          {/* Link Columns */}
          {Object.values(footerLinks).map((section) => (
            <div key={section.title}>
              <h2 className="label-text text-cream/70 mb-4 tracking-widest">
                {section.title}
              </h2>
              <ul className="space-y-3">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="body-sm text-cream/60 hover:text-cream transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-cream/10">
        <div className="container-page py-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-xs text-cream/65">
            &copy; {year ?? 2026} Modest Chic by Hira &amp; Muqadas. All rights reserved.
          </p>
          <p className="text-xs text-cream/65">
            Thoughtful modest style
          </p>
        </div>
      </div>
    </footer>
  );
}
