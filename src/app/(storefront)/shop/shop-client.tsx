"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import Image from "next/image";
import { SlidersHorizontal, X, Search, ChevronDown } from "lucide-react";
import { ProductCard } from "@/components/ui/product-card";
import { fabrics, colorFamilies } from "@/lib/data";
import { useCatalog } from "@/lib/context/catalog-context";
import { Button } from "@/components/ui/button";

type SortOption = "featured" | "newest" | "popular" | "price-low" | "price-high";

function PriceRangeFilter({
  minPrice,
  maxPrice,
  setMinPrice,
  setMaxPrice,
}: {
  minPrice: string;
  maxPrice: string;
  setMinPrice: (value: string) => void;
  setMaxPrice: (value: string) => void;
}) {
  return (
    <div>
      <p className="label-text text-charcoal mb-3">Price range (PKR)</p>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-charcoal/75">
          Minimum
          <input
            type="number"
            min="0"
            step="1"
            inputMode="numeric"
            aria-label="Minimum price in PKR"
            placeholder="0"
            value={minPrice}
            onChange={(event) => setMinPrice(event.target.value)}
            className="mt-1 w-full rounded-lg border border-sand bg-white px-3 py-2 text-sm text-charcoal focus:border-terracotta/40 focus:outline-none focus:ring-2 focus:ring-terracotta/20"
          />
        </label>
        <label className="text-xs text-charcoal/75">
          Maximum
          <input
            type="number"
            min="0"
            step="1"
            inputMode="numeric"
            aria-label="Maximum price in PKR"
            placeholder="No limit"
            value={maxPrice}
            onChange={(event) => setMaxPrice(event.target.value)}
            className="mt-1 w-full rounded-lg border border-sand bg-white px-3 py-2 text-sm text-charcoal focus:border-terracotta/40 focus:outline-none focus:ring-2 focus:ring-terracotta/20"
          />
        </label>
      </div>
    </div>
  );
}

export default function ShopClient({ initialCategory, initialQuery }: { initialCategory: string | null; initialQuery: string }) {
  const { products, categories, mode, error, retry, loadPopularityOrder } = useCatalog();
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const mobileFiltersTriggerRef = useRef<HTMLButtonElement>(null);
  const mobileFiltersRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(initialCategory);
  const [selectedFabrics, setSelectedFabrics] = useState<string[]>([]);
  const [selectedColors, setSelectedColors] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<SortOption>("featured");
  const [showSortDropdown, setShowSortDropdown] = useState(false);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [onSaleOnly, setOnSaleOnly] = useState(false);
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [popularityOrder, setPopularityOrder] = useState<string[]>([]);

  useEffect(() => {
    if (!mobileFiltersOpen) return;
    const drawer = mobileFiltersRef.current;
    const trigger = mobileFiltersTriggerRef.current;
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
        setMobileFiltersOpen(false);
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
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      previousBackgroundAttributes.forEach(({ element, inert, ariaHidden }) => {
        if (!inert) element.removeAttribute("inert");
        if (ariaHidden === null) element.removeAttribute("aria-hidden");
        else element.setAttribute("aria-hidden", ariaHidden);
      });
      trigger?.focus();
    };
  }, [mobileFiltersOpen]);

  useEffect(() => {
    if (sortBy !== "popular") return;
    let active = true;
    void loadPopularityOrder().then((order) => {
      if (active) setPopularityOrder(order);
    });
    return () => { active = false; };
  }, [sortBy, loadPopularityOrder]);

  const toggleFabric = (fabric: string) => {
    setSelectedFabrics((prev) =>
      prev.includes(fabric) ? prev.filter((f) => f !== fabric) : [...prev, fabric]
    );
  };

  const toggleColor = (color: string) => {
    setSelectedColors((prev) =>
      prev.includes(color) ? prev.filter((c) => c !== color) : [...prev, color]
    );
  };

  const clearFilters = () => {
    setSelectedCategory(null);
    setSelectedFabrics([]);
    setSelectedColors([]);
    setInStockOnly(false);
    setOnSaleOnly(false);
    setMinPrice("");
    setMaxPrice("");
    setSearchQuery("");
  };

  const hasActiveFilters =
    selectedCategory ||
    selectedFabrics.length > 0 ||
    selectedColors.length > 0 ||
    inStockOnly ||
    onSaleOnly ||
    minPrice !== "" ||
    maxPrice !== "" ||
    searchQuery;

  const filteredProducts = useMemo(() => {
    let result = [...products];

    // Search
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          p.fabric.toLowerCase().includes(q) ||
          p.tags.some((t) => t.includes(q)) ||
          p.variants.some((v) => v.name.toLowerCase().includes(q))
      );
    }

    // Category
    if (selectedCategory) {
      result = result.filter((p) => (p.categories ?? [p.category]).includes(selectedCategory));
    }

    // Fabric
    if (selectedFabrics.length > 0) {
      result = result.filter((p) =>
        selectedFabrics.some(
          (f) => p.fabric.toLowerCase().includes(f.toLowerCase())
        )
      );
    }

    // Color families
    if (selectedColors.length > 0) {
      result = result.filter((p) =>
        p.variants.some((v) =>
          selectedColors.some((c) => {
            const color = v.color.toLowerCase();
            const match: Record<string, string[]> = {
              "nude & beige": ["sand", "beige", "taupe", "mushroom", "neutral", "champagne"],
              "dusty rose": ["rose", "blush", "pink"],
              terracotta: ["terracotta"],
              "deep rust": ["rust", "espresso"],
              "olive & sage": ["olive", "sage", "botanical"],
              "cream & white": ["cream", "white", "ivory"],
              "mauve grey": ["mauve", "grey", "charcoal"],
            };
            return (match[c] ?? [c]).some((name) => color.includes(name));
          })
        )
      );
    }

    // In stock only
    if (inStockOnly) {
      result = result.filter((p) =>
        p.variants.some((v) => v.stock > 0)
      );
    }

    // On sale only
    if (onSaleOnly) {
      result = result.filter((p) =>
        p.variants.some((v) => v.salePrice !== undefined)
      );
    }

    const lowerPrice = minPrice === "" ? null : Number(minPrice);
    const upperPrice = maxPrice === "" ? null : Number(maxPrice);
    if (lowerPrice !== null || upperPrice !== null) {
      result = result.filter((product) =>
        product.variants.some((variant) => {
          const price = variant.salePrice ?? variant.price;
          return (lowerPrice === null || price >= lowerPrice) &&
            (upperPrice === null || price <= upperPrice);
        })
      );
    }

    // Sort
    const popularityRanks = new Map(popularityOrder.map((slug, index) => [slug, index]));
    switch (sortBy) {
      case "newest":
        result.sort((a, b) => (b.isNew ? 1 : 0) - (a.isNew ? 1 : 0));
        break;
      case "popular":
        result.sort((a, b) => {
          const aRank = popularityRanks.get(a.slug);
          const bRank = popularityRanks.get(b.slug);
          const aPosition = aRank ?? Number.MAX_SAFE_INTEGER;
          const bPosition = bRank ?? Number.MAX_SAFE_INTEGER;
          return aPosition - bPosition || Number(b.isBestSeller) - Number(a.isBestSeller);
        });
        break;
      case "price-low":
        result.sort(
          (a, b) =>
            Math.min(...a.variants.map((v) => v.salePrice ?? v.price)) -
            Math.min(...b.variants.map((v) => v.salePrice ?? v.price))
        );
        break;
      case "price-high":
        result.sort(
          (a, b) =>
            Math.max(...b.variants.map((v) => v.salePrice ?? v.price)) -
            Math.max(...a.variants.map((v) => v.salePrice ?? v.price))
        );
        break;
      default:
        // Featured: best sellers and new first
        result.sort(
          (a, b) =>
            (b.isBestSeller ? 2 : 0) +
            (b.isNew ? 1 : 0) -
            ((a.isBestSeller ? 2 : 0) + (a.isNew ? 1 : 0))
        );
    }

    return result;
  }, [products, popularityOrder, searchQuery, selectedCategory, selectedFabrics, selectedColors, inStockOnly, onSaleOnly, minPrice, maxPrice, sortBy]);

  if (mode === "live" && products.length === 0) return <div className="container-page min-h-[60vh] py-20 text-center"><h1 className="heading-lg">Our collection is being prepared</h1><p className="mt-5 text-charcoal/75">Real products, prices and photographs will appear here soon.</p><a className="mt-6 inline-block underline" href="/contact">Contact us on WhatsApp</a></div>;

  if (mode === "loading") return <div className="container-page py-20" role="status">Loading products…</div>;
  if (mode === "error") return <div className="container-page py-20" role="alert"><p>{error}</p><button type="button" onClick={retry} className="mt-4 underline">Retry</button></div>;

  return (
    <>
    <div id="shop-content" className="min-h-screen bg-cream">
      {/* Page Header */}
      <div className="border-b border-sand/50 bg-[#f3e9e3]">
        <div className="container-page grid items-center gap-8 py-8 md:grid-cols-[1fr_0.72fr] md:gap-14 md:py-10">
          <div className="py-2">
            <p className="label-text mb-3 text-terracotta">The Modest Chic edit</p>
            <h1 className="heading-lg mb-3 text-charcoal">Hijabs, gifts &amp; little details</h1>
            <p className="body-base max-w-lg text-charcoal/75">
              Discover thoughtfully chosen hijabs and gift sets from Modest Chic by Hira &amp; Muqadas. Find your shade, browse the edit, and choose something lovely for someone you love.
            </p>
          </div>
          <div className="relative hidden aspect-[2.5/1] overflow-hidden rounded-2xl md:block">
            <Image src="/images/modest-chic-gift-edit.webp" alt="A selection of Modest Chic gift-ready hijab colors" fill loading="eager" sizes="(max-width: 1024px) 40vw, 30vw" className="object-cover object-center" />
          </div>
        </div>
      </div>

      <div className="container-page py-8">
        <div className="flex gap-8">
          {/* -------- DESKTOP FILTERS -------- */}
          <aside className="hidden lg:block w-64 flex-shrink-0">
            <div className="sticky top-24 space-y-8">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-charcoal/75" />
                <input
                  type="text"
                  placeholder="Search products or shades..."
                  aria-label="Search products"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 text-sm bg-white border border-sand rounded-lg text-charcoal placeholder:text-charcoal/75 focus:outline-none focus:ring-2 focus:ring-terracotta/20 focus:border-terracotta/40"
                />
              </div>

              {/* Category */}
              <div>
                <p className="label-text text-charcoal mb-3">Category</p>
                <div className="space-y-1.5">
                  {categories.map((cat) => (
                    <button
                      key={cat.id}
                      aria-label={`${cat.title} (${products.filter((product) => (product.categories ?? [product.category]).includes(cat.slug)).length})`}
                      onClick={() =>
                        setSelectedCategory(
                          selectedCategory === cat.slug ? null : cat.slug
                        )
                      }
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${
                        selectedCategory === cat.slug
                          ? "bg-terracotta/10 text-terracotta font-medium"
                          : "text-charcoal/75 hover:text-charcoal hover:bg-warm-cream"
                      }`}
                    >
                      {cat.title}
                      <span className="text-charcoal/75 ml-1">({products.filter((product) => (product.categories ?? [product.category]).includes(cat.slug)).length})</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Fabric */}
              <PriceRangeFilter minPrice={minPrice} maxPrice={maxPrice} setMinPrice={setMinPrice} setMaxPrice={setMaxPrice} />

              {/* Fabric */}
              <div>
                <p className="label-text text-charcoal mb-3">Fabric</p>
                <div className="space-y-1.5">
                  {fabrics.map((fabric) => (
                    <label
                      key={fabric}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer hover:bg-warm-cream transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={selectedFabrics.includes(fabric)}
                        onChange={() => toggleFabric(fabric)}
                        className="w-4 h-4 rounded border-sand text-terracotta focus:ring-terracotta/30"
                      />
                      <span className="text-sm text-charcoal/70">{fabric}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Color */}
              <div>
                <p className="label-text text-charcoal mb-3">Color</p>
                <div className="space-y-1.5">
                  {colorFamilies.map((color) => (
                    <label
                      key={color.name}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer hover:bg-warm-cream transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={selectedColors.includes(color.name.toLowerCase())}
                        onChange={() => toggleColor(color.name.toLowerCase())}
                        className="w-4 h-4 rounded border-sand text-terracotta focus:ring-terracotta/30"
                      />
                      <span
                        className="w-4 h-4 rounded-full border border-sand"
                        style={{ backgroundColor: color.hex }}
                      />
                      <span className="text-sm text-charcoal/70">{color.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Quick filters */}
              <div className="space-y-2">
                <label className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-warm-cream rounded-lg transition-colors">
                  <input
                    type="checkbox"
                    checked={inStockOnly}
                    onChange={() => setInStockOnly(!inStockOnly)}
                    className="w-4 h-4 rounded border-sand text-terracotta focus:ring-terracotta/30"
                  />
                  <span className="text-sm text-charcoal/70">In Stock Only</span>
                </label>
                <label className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-warm-cream rounded-lg transition-colors">
                  <input
                    type="checkbox"
                    checked={onSaleOnly}
                    onChange={() => setOnSaleOnly(!onSaleOnly)}
                    className="w-4 h-4 rounded border-sand text-terracotta focus:ring-terracotta/30"
                  />
                  <span className="text-sm text-charcoal/70">On Sale</span>
                </label>
              </div>

              {/* Clear filters */}
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="text-sm text-terracotta hover:text-rust font-medium flex items-center gap-1"
                >
                  <X className="w-3.5 h-3.5" />
                  Clear All Filters
                </button>
              )}
            </div>
          </aside>

          {/* -------- PRODUCTS GRID -------- */}
          <div className="flex-1 min-w-0">
            {/* Toolbar */}
            <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
              <div className="flex items-center gap-3">
                {/* Mobile Filter Button */}
                <button
                  ref={mobileFiltersTriggerRef}
                  onClick={() => setMobileFiltersOpen(true)}
                  className="lg:hidden flex items-center gap-2 px-4 py-2.5 border border-sand rounded-xl text-sm text-charcoal/70 hover:bg-warm-cream transition-colors"
                  aria-label="Open filters"
                >
                  <SlidersHorizontal className="w-4 h-4" />
                  Filters
                  {hasActiveFilters && (
                    <span className="w-5 h-5 bg-terracotta text-cream text-[10px] rounded-full flex items-center justify-center">
                      !
                    </span>
                  )}
                </button>

                <p className="text-sm text-charcoal/75">
                  {filteredProducts.length}{" "}
                  {filteredProducts.length === 1 ? "product" : "products"}
                </p>
              </div>

              {/* Sort */}
              <div className="relative">
                <button
                  onClick={() => setShowSortDropdown(!showSortDropdown)}
                  className="flex items-center gap-2 px-4 py-2.5 border border-sand rounded-xl text-sm text-charcoal/70 hover:bg-warm-cream transition-colors"
                  aria-expanded={showSortDropdown}
                >
                  Sort:{" "}
                  {sortBy === "featured"
                    ? "Featured"
                    : sortBy === "newest"
                    ? "Newest"
                    : sortBy === "price-low"
                    ? "Price: Low to High"
                    : sortBy === "price-high"
                    ? "Price: High to Low"
                    : sortBy === "popular"
                    ? "Popular"
                    : "Featured"}
                  <ChevronDown className="w-4 h-4" />
                </button>

                {showSortDropdown && (
                  <div className="absolute right-0 top-full mt-1 bg-cream border border-sand/50 rounded-xl shadow-xl shadow-charcoal/5 py-1 min-w-[200px] z-20 animate-scale-in">
                    {[
                      { value: "featured" as SortOption, label: "Featured" },
                      { value: "popular" as SortOption, label: "Popular" },
                      { value: "newest" as SortOption, label: "Newest" },
                      { value: "price-low" as SortOption, label: "Price: Low to High" },
                      { value: "price-high" as SortOption, label: "Price: High to Low" },
                    ].map((option) => (
                      <button
                        key={option.value}
                        onClick={() => {
                          setSortBy(option.value);
                          setShowSortDropdown(false);
                        }}
                        className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                          sortBy === option.value
                            ? "text-terracotta bg-terracotta/5 font-medium"
                            : "text-charcoal/70 hover:text-charcoal hover:bg-warm-cream"
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Active filter chips */}
            {hasActiveFilters && (
              <div className="flex flex-wrap gap-2 mb-6">
                {selectedCategory && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-terracotta/10 text-terracotta text-xs font-medium rounded-full">
                    {categories.find((c) => c.slug === selectedCategory)?.title}
                    <button onClick={() => setSelectedCategory(null)} aria-label="Remove category filter">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                )}
                {selectedFabrics.map((f) => (
                  <span
                    key={f}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-terracotta/10 text-terracotta text-xs font-medium rounded-full"
                  >
                    {f}
                    <button onClick={() => toggleFabric(f)} aria-label={`Remove ${f} filter`}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {selectedColors.map((c) => (
                  <span
                    key={c}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-terracotta/10 text-terracotta text-xs font-medium rounded-full capitalize"
                  >
                    {c}
                    <button onClick={() => toggleColor(c)} aria-label={`Remove ${c} filter`}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {searchQuery && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-terracotta/10 text-terracotta text-xs font-medium rounded-full">
                    Search: {searchQuery}
                    <button onClick={() => setSearchQuery("")} aria-label="Clear search"><X className="w-3 h-3" /></button>
                  </span>
                )}
                {(minPrice !== "" || maxPrice !== "") && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-terracotta/10 text-terracotta text-xs font-medium rounded-full">
                    Price: {minPrice || "0"}–{maxPrice || "∞"} PKR
                    <button onClick={() => { setMinPrice(""); setMaxPrice(""); }} aria-label="Remove price range filter">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                )}
                {(inStockOnly || onSaleOnly) && (
                  <button onClick={() => { setInStockOnly(false); setOnSaleOnly(false); }} className="px-3 py-1.5 text-xs text-terracotta underline underline-offset-2">Clear availability filters</button>
                )}
              </div>
            )}

            {/* Product Grid */}
            <section aria-labelledby="shop-products-heading">
              <h2 id="shop-products-heading" className="sr-only">Products</h2>
              {filteredProducts.length > 0 ? (
                <div className="grid grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
                  {filteredProducts.map((product, index) => (
                    <ProductCard key={product.id} product={product} preloadImage={index === 0} eagerImage={index < 4} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-20">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-warm-cream mb-4">
                    <Search className="w-6 h-6 text-charcoal/60" />
                  </div>
                  <h3 className="heading-sm text-charcoal mb-2">{selectedCategory === "sets" ? "Gift sets are coming soon" : "No products found"}</h3>
                  <p className="text-charcoal/75 mb-6">
                    {selectedCategory === "sets" ? "Explore our hijabs and accessories while we prepare this collection." : "Try adjusting your search or filters to find what you&apos;re looking for."}
                  </p>
                  <Button variant="outline" onClick={clearFilters}>
                    Clear All Filters
                  </Button>
                </div>
              )}
            </section>
          </div>
        </div>
      </div>
    </div>

      {/* -------- MOBILE FILTER DRAWER -------- */}
      {mobileFiltersOpen && typeof document !== "undefined" && createPortal((
        <div className="fixed inset-0 z-[100] lg:hidden">
          <div
            className="absolute inset-0 bg-charcoal/40 backdrop-blur-sm animate-fade-in"
            onClick={() => setMobileFiltersOpen(false)}
            aria-hidden="true"
          />
          <div ref={mobileFiltersRef} role="dialog" aria-modal="true" aria-label="Filter products" className="absolute inset-y-0 right-0 w-[85vw] max-w-sm bg-cream shadow-2xl animate-slide-in-right overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-sand/50">
              <h2 className="font-medium text-charcoal">Filters</h2>
              <button
                onClick={() => setMobileFiltersOpen(false)}
                className="p-2 text-charcoal/70 hover:text-charcoal rounded-lg"
                aria-label="Close filters"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-8">
              {/* Search */}
              <div>
                <p className="label-text text-charcoal mb-3">Search</p>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-charcoal/75" />
                  <input
                    type="text"
                    placeholder="Search products..."
                    aria-label="Search products"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 text-sm bg-warm-cream border border-sand rounded-xl focus:outline-none focus:ring-2 focus:ring-terracotta/20"
                  />
                </div>
              </div>

              {/* Category */}
              <div>
                <p className="label-text text-charcoal mb-3">Category</p>
                <div className="space-y-1">
                  {categories.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() =>
                        setSelectedCategory(
                          selectedCategory === cat.slug ? null : cat.slug
                        )
                      }
                      className={`w-full text-left px-3 py-3 rounded-lg text-sm transition-all ${
                        selectedCategory === cat.slug
                          ? "bg-terracotta/10 text-terracotta font-medium"
                          : "text-charcoal/70 hover:bg-warm-cream"
                      }`}
                    >
                      {cat.title}
                    </button>
                  ))}
                </div>
              </div>

              {/* Fabric */}
              <PriceRangeFilter minPrice={minPrice} maxPrice={maxPrice} setMinPrice={setMinPrice} setMaxPrice={setMaxPrice} />

              {/* Fabric */}
              <div>
                <p className="label-text text-charcoal mb-3">Fabric</p>
                <div className="space-y-1">
                  {fabrics.map((fabric) => (
                    <label
                      key={fabric}
                      className="flex items-center gap-3 px-3 py-3 rounded-lg cursor-pointer hover:bg-warm-cream"
                    >
                      <input
                        type="checkbox"
                        checked={selectedFabrics.includes(fabric)}
                        onChange={() => toggleFabric(fabric)}
                        className="w-5 h-5 rounded border-sand text-terracotta"
                      />
                      <span className="text-sm">{fabric}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Color */}
              <div>
                <p className="label-text text-charcoal mb-3">Color</p>
                <div className="space-y-1">
                  {colorFamilies.map((color) => (
                    <label
                      key={color.name}
                      className="flex items-center gap-3 px-3 py-3 rounded-lg cursor-pointer hover:bg-warm-cream"
                    >
                      <input
                        type="checkbox"
                        checked={selectedColors.includes(color.name.toLowerCase())}
                        onChange={() => toggleColor(color.name.toLowerCase())}
                        className="w-5 h-5 rounded border-sand text-terracotta"
                      />
                      <span
                        className="w-5 h-5 rounded-full border border-sand"
                        style={{ backgroundColor: color.hex }}
                      />
                      <span className="text-sm">{color.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Quick filters */}
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={inStockOnly}
                    onChange={() => setInStockOnly(!inStockOnly)}
                    className="w-5 h-5 rounded border-sand text-terracotta"
                  />
                  <span className="text-sm">In Stock Only</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={onSaleOnly}
                    onChange={() => setOnSaleOnly(!onSaleOnly)}
                    className="w-5 h-5 rounded border-sand text-terracotta"
                  />
                  <span className="text-sm">On Sale</span>
                </label>
              </div>
            </div>

            {/* Bottom Actions */}
            <div className="sticky bottom-0 p-4 border-t border-sand/50 bg-cream flex gap-3">
              <button
                onClick={clearFilters}
                className="flex-1 py-3 text-sm font-medium text-charcoal/75 hover:text-charcoal border border-sand rounded-xl"
              >
                Clear All
              </button>
              <button
                onClick={() => setMobileFiltersOpen(false)}
                className="flex-1 py-3 text-sm font-medium bg-charcoal text-cream rounded-xl"
              >
                Show {filteredProducts.length} Results
              </button>
            </div>
          </div>
        </div>
      ), document.body)}
    </>
  );
}
