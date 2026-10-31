import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Staff · Modest Chic", robots: { index: false, follow: false } };

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-cream text-charcoal">
    <header className="border-b border-sand bg-white"><div className="container-page flex items-center justify-between py-5">
      <Link href="/admin" className="font-serif text-xl tracking-wide">Modest Chic <span className="font-sans text-xs uppercase tracking-widest text-terracotta">Staff</span></Link>
      <Link href="/" className="text-sm text-charcoal/75 hover:text-charcoal">Storefront</Link>
    </div></header>
    <main className="container-page py-10">{children}</main>
  </div>;
}
