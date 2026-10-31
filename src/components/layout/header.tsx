"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  Search,
  ShoppingBag,
  Menu,
  X,
  ChevronDown,
  Heart,
  UserRound,
} from "lucide-react";
import { useCart } from "@/lib/context/cart-context";
import { useWishlist } from "@/lib/context/wishlist-context";
import { isStaticStorefront } from "@/lib/storefront-mode";
import { useCatalog } from "@/lib/context/catalog-context";

const previewNavLinks = [
  { label: "Home", href: "/" },
  { label: "Shop", href: "/shop" },
  {
    label: "Collections",
    href: "#",
    children: [
      { label: "New Arrivals", href: "/collections/new-arrivals" },
      { label: "Featured Pieces", href: "/collections/best-sellers" },
      { label: "Signature Collection", href: "/collections/signature-neutrals" },
      { label: "Everyday Essentials", href: "/collections/everyday-essentials" },
      { label: "Luxe Occasion", href: "/collections/luxe-occasion" },
    ],
  },
  {
    label: "Categories",
    href: "#",
    children: [
      { label: "Hijabs", href: "/shop?category=hijabs" },
      { label: "Accessories", href: "/shop?category=accessories" },
      { label: "Gift Sets", href: "/shop?category=sets" },
    ],
  },
  { label: "About", href: "/about" },
];

export function Header() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const mobileMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const { itemCount: cartCount } = useCart();
  const { count: wishlistCount } = useWishlist();
  const { mode, categories, collections } = useCatalog();
  const navLinks = mode === "live" ? [
    { label: "Home", href: "/" },
    { label: "Shop", href: "/shop" },
    { label: "Collections", href: "#", children: collections.map((item) => ({ label: item.title, href: `/collections/${item.slug}` })) },
    { label: "Categories", href: "#", children: categories.map((item) => ({ label: item.title, href: `/shop?category=${encodeURIComponent(item.slug)}` })) },
    { label: "About", href: "/about" },
  ] : previewNavLinks;

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const drawer = mobileMenuRef.current;
    const menuTrigger = mobileMenuTriggerRef.current;
    const backgroundElements = ["site-announcement", "site-header", "site-main", "site-footer"]
      .map((id) => document.getElementById(id))
      .filter((element): element is HTMLElement => element instanceof HTMLElement);
    const previousBackgroundAttributes = backgroundElements.map((element) => ({
      element,
      inert: element.hasAttribute("inert"),
      ariaHidden: element.getAttribute("aria-hidden"),
    }));
    const previousBodyOverflow = document.body.style.overflow;
    const getFocusableElements = () => Array.from(
      drawer?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    );
    getFocusableElements()[0]?.focus();
    backgroundElements.forEach((element) => {
      element.setAttribute("inert", "");
      element.setAttribute("aria-hidden", "true");
    });
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const focusableElements = getFocusableElements();
      const first = focusableElements[0];
      const last = focusableElements.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && (document.activeElement === first || !drawer?.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !drawer?.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      previousBackgroundAttributes.forEach(({ element, inert, ariaHidden }) => {
        if (!inert) element.removeAttribute("inert");
        if (ariaHidden === null) element.removeAttribute("aria-hidden");
        else element.setAttribute("aria-hidden", ariaHidden);
      });
      menuTrigger?.focus();
    };
  }, [mobileMenuOpen]);

  return (
    <>
      {/* Announcement Bar */}
      <div id="site-announcement" className="bg-charcoal text-cream text-center text-xs tracking-wider py-2 px-4 font-medium">
        <span>{mode === "live" ? "Modest Chic · Explore the collection" : "Store preview · Explore the collection · Ordering coming soon"}</span>
      </div>

      {/* Header */}
      <header
        id="site-header"
        className={`
          sticky top-0 z-50 transition-all duration-500
          ${
            isScrolled
              ? "bg-cream/95 backdrop-blur-md shadow-sm border-b border-sand/50"
              : "bg-cream border-b border-transparent"
          }
        `}
      >
        <div className="container-page">
          <div className="flex items-center justify-between h-16 md:h-20">
            {/* Mobile Menu Toggle */}
            <button
              ref={mobileMenuTriggerRef}
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 -ml-2 text-charcoal hover:text-terracotta transition-colors"
              aria-label="Open menu"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-navigation"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Logo */}
            <Link
              href="/"
              className="group flex flex-shrink-0 items-center gap-2.5"
              onClick={() => setMobileMenuOpen(false)}
            >
              <span className="relative h-10 w-10 shrink-0 overflow-hidden rounded-full border border-[#8c706a]/25 bg-[#eee8e3] md:h-12 md:w-12">
                <Image src="/images/modest-chic-official-logo.jpeg" alt="" fill sizes="48px" className="object-cover object-[center_16%]" />
              </span>
              <span className="flex flex-col">
                <span className="font-display text-base uppercase tracking-[0.15em] text-charcoal transition-colors group-hover:text-terracotta md:text-lg">Modest Chic</span>
                  <span className="text-[9px] uppercase tracking-[0.18em] text-charcoal/75">by Hira &amp; Muqadas</span>
              </span>
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden lg:flex items-center gap-1">
              {navLinks.map((link) => {
                if (link.children) {
                  return (
                    <div
                      key={link.label}
                      className="relative"
                      onMouseEnter={() => setActiveDropdown(link.label)}
                      onMouseLeave={() => setActiveDropdown(null)}
                      onBlur={(event) => {
                        if (!event.currentTarget.contains(event.relatedTarget)) setActiveDropdown(null);
                      }}
                    >
                      <button
                        type="button"
                        aria-expanded={activeDropdown === link.label}
                        aria-haspopup="menu"
                        onClick={() => setActiveDropdown(activeDropdown === link.label ? null : link.label)}
                        className="flex items-center gap-1 px-3 py-2 text-sm text-charcoal/70 hover:text-charcoal transition-colors rounded-lg hover:bg-sand/50"
                      >
                        {link.label}
                        <ChevronDown className="w-3.5 h-3.5 opacity-50" />
                      </button>
                      {activeDropdown === link.label && (
                        <div className="absolute top-full left-0 mt-1 bg-cream border border-sand/50 rounded-xl shadow-xl shadow-charcoal/5 py-2 min-w-[200px] animate-scale-in" onKeyDown={(event) => { if (event.key === "Escape") setActiveDropdown(null); }}>
                          {link.children.map((child) => (
                            <Link
                              key={child.label}
                              href={child.href}
                              onClick={() => setActiveDropdown(null)}
                              className="block px-4 py-2.5 text-sm text-charcoal/70 hover:text-charcoal hover:bg-warm-cream transition-colors"
                            >
                              {child.label}
                            </Link>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                }
                return (
                  <Link
                    key={link.label}
                    href={link.href}
                    className="px-3 py-2 text-sm text-charcoal/70 hover:text-charcoal transition-colors rounded-lg hover:bg-sand/50"
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>

            {/* Right Actions */}
            <div className="flex items-center gap-1 md:gap-2">
              {/* Search */}
              <button
                onClick={() => setSearchOpen(!searchOpen)}
                className="p-2 text-charcoal/70 hover:text-charcoal transition-colors rounded-lg hover:bg-sand/50"
                aria-label="Search"
                aria-expanded={searchOpen}
              >
                <Search className="w-5 h-5" />
              </button>

              {/* Wishlist */}
              {!isStaticStorefront() && <Link href="/account" className="hidden sm:flex p-2 text-charcoal/70 hover:text-charcoal" aria-label="Account"><UserRound className="w-5 h-5" /></Link>}
              <Link
                href="/wishlist"
                className="relative hidden sm:flex p-2 text-charcoal/70 hover:text-charcoal transition-colors rounded-lg hover:bg-sand/50"
                aria-label="Wishlist"
              >
                <Heart className="w-5 h-5" />
                {wishlistCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-dusty-rose text-cream text-[10px] font-bold rounded-full flex items-center justify-center animate-scale-in">
                    {wishlistCount > 9 ? "9+" : wishlistCount}
                  </span>
                )}
              </Link>

              {/* Cart */}
              <Link
                href="/cart"
                className="relative p-2 text-charcoal/70 hover:text-charcoal transition-colors rounded-lg hover:bg-sand/50"
                aria-label="Cart"
              >
                <ShoppingBag className="w-5 h-5" />
                {cartCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-terracotta text-cream text-[10px] font-bold rounded-full flex items-center justify-center animate-scale-in">
                    {cartCount}
                  </span>
                )}
              </Link>
            </div>
          </div>

          {/* Search Bar */}
          {searchOpen && (
            <div className="pb-4 animate-fade-in-up">
              <form action="/shop" method="GET" className="relative" onKeyDown={(event) => { if (event.key === "Escape") setSearchOpen(false); }}>
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-charcoal/75" />
                <input
                  type="text"
                  name="q"
                  aria-label="Search the catalog"
                  placeholder="Search hijabs, fabrics, colors..."
                  className="w-full pl-12 pr-24 py-3.5 bg-warm-cream border border-sand rounded-xl text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40 transition-all"
                  autoFocus
                />
                <button type="submit" className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg bg-charcoal px-4 py-2 text-xs font-medium text-cream hover:bg-deep-rust">Search</button>
              </form>
            </div>
          )}
        </div>
      </header>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-[100] lg:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-charcoal/40 backdrop-blur-sm animate-fade-in"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Drawer */}
          <div
            ref={mobileMenuRef}
            id="mobile-navigation"
            role="dialog"
            aria-modal="true"
            aria-label="Site navigation"
            className="absolute inset-y-0 left-0 w-[85vw] max-w-sm bg-cream shadow-2xl animate-slide-in-right"
          >
            <div className="flex items-center justify-between p-4 border-b border-sand/50">
              <span className="flex items-center gap-2">
                <span className="relative h-9 w-9 shrink-0 overflow-hidden rounded-full border border-[#8c706a]/25 bg-[#eee8e3]">
                  <Image src="/images/modest-chic-official-logo.jpeg" alt="" fill sizes="36px" className="object-cover object-[center_16%]" />
                </span>
                <span className="flex flex-col">
                  <span className="font-display text-base uppercase tracking-[0.15em] text-charcoal">Modest Chic</span>
                  <span className="text-[9px] uppercase tracking-[0.15em] text-charcoal/75">by Hira &amp; Muqadas</span>
                </span>
              </span>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-2 text-charcoal/70 hover:text-charcoal transition-colors rounded-lg"
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-1 overflow-y-auto max-h-[calc(100vh-80px)]">
              {navLinks.map((link) => {
                if (link.children) {
                  return (
                    <div key={link.label} className="py-1">
                      <p className="label-text text-charcoal/75 px-3 py-2">
                        {link.label}
                      </p>
                      {link.children.map((child) => (
                        <Link
                          key={child.label}
                          href={child.href}
                          onClick={() => setMobileMenuOpen(false)}
                          className="block px-3 py-3 text-base text-charcoal/70 hover:text-charcoal hover:bg-warm-cream rounded-lg transition-colors"
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  );
                }
                return (
                  <Link
                    key={link.label}
                    href={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-3 text-base text-charcoal/70 hover:text-charcoal hover:bg-warm-cream rounded-lg transition-colors"
                  >
                    {link.label}
                  </Link>
                );
              })}

              <hr className="my-4 border-sand/50" />
              {!isStaticStorefront() && <Link href="/account" onClick={() => setMobileMenuOpen(false)} className="flex items-center gap-3 px-3 py-3 text-base text-charcoal/70">Account</Link>}

              <Link
                href="/wishlist"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-3 px-3 py-3 text-base text-charcoal/70 hover:text-charcoal hover:bg-warm-cream rounded-lg transition-colors"
              >
                <Heart className="w-4 h-4" />
                Wishlist
                {wishlistCount > 0 && (
                  <span className="ml-auto text-xs bg-dusty-rose/10 text-dusty-rose px-2 py-0.5 rounded-full font-medium">
                    {wishlistCount}
                  </span>
                )}
              </Link>
              <Link
                href="/cart"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-3 px-3 py-3 text-base text-charcoal/70 hover:text-charcoal hover:bg-warm-cream rounded-lg transition-colors"
              >
                <ShoppingBag className="w-4 h-4" />
                Cart
                {cartCount > 0 && (
                  <span className="ml-auto text-xs bg-terracotta/10 text-terracotta px-2 py-0.5 rounded-full font-medium">
                    {cartCount}
                  </span>
                )}
              </Link>

              <hr className="my-4 border-sand/50" />

              <Link
                href="/about"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-3 text-base text-charcoal/70 hover:text-charcoal hover:bg-warm-cream rounded-lg transition-colors"
              >
                About Us
              </Link>
              <Link
                href="/contact"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-3 text-base text-charcoal/70 hover:text-charcoal hover:bg-warm-cream rounded-lg transition-colors"
              >
                Contact
              </Link>
              <Link
                href="/faq"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-3 text-base text-charcoal/70 hover:text-charcoal hover:bg-warm-cream rounded-lg transition-colors"
              >
                FAQ
              </Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
