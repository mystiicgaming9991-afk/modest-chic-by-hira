"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Heart, PackageCheck, Sparkles } from "lucide-react";
import { ProductCard } from "@/components/ui/product-card";
import { useCatalog } from "@/lib/context/catalog-context";

const stories = [
  {
    number: "01",
    title: "Made for your everyday",
    description: "Soft, easy-to-style hijabs in colors you’ll reach for again and again.",
    href: "/shop?category=hijabs",
  },
  {
    number: "02",
    title: "A thoughtful little gift",
    description: "Explore coordinated sets, finished with the details that make them special.",
    href: "/shop?category=sets",
  },
  {
    number: "03",
    title: "A little more you",
    description: "Find a shade and a drape that feel like they were made for you.",
    href: "/collections/new-arrivals",
  },
];

export default function HomePage() {
  const { products, mode } = useCatalog();
  const bestSellers = (mode === "live" ? products : products.filter((product) => product.isBestSeller)).slice(0, 4);

  return (
    <div className="overflow-hidden bg-cream">
      <section className="relative min-h-[680px] bg-[#f1eae5]">
        <div className="absolute inset-0 md:left-[43%]">
          <Image
            src="/images/modest-chic-campaign.webp"
            alt="Modest Chic campaign featuring a model in a black hijab and a selection of folded colors"
            fill
            preload
            sizes="(max-width: 768px) 100vw, 57vw"
            className="object-cover object-[center_38%]"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-charcoal/60 via-charcoal/10 to-transparent md:bg-gradient-to-r md:from-[#f1eae5] md:via-[#f1eae5]/20 md:to-transparent" />
        </div>

        <div className="container-page relative z-10 grid min-h-[680px] items-end pb-12 pt-24 md:grid-cols-[1fr_0.8fr] md:items-center md:py-20">
          <div className="max-w-xl rounded-2xl bg-[#f1eae5]/90 p-6 backdrop-blur-sm md:bg-transparent md:p-0">
            <div className="mb-6 inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-terracotta">
              <Sparkles className="h-4 w-4" />
              Modest Chic by Hira &amp; Muqadas
            </div>
            <h1 className="font-display text-5xl font-normal leading-[1.08] tracking-tight text-charcoal md:text-7xl">
              The comfort of modesty. <span className="italic text-terracotta">The joy of you.</span>
            </h1>
            <p className="mt-6 max-w-md text-base leading-7 text-charcoal/75 md:text-lg">
              Thoughtfully chosen hijabs and gift sets for the moments that make up your day.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/shop" className="inline-flex items-center gap-3 rounded-full bg-[#564340] px-6 py-3.5 text-sm font-medium text-cream transition-colors hover:bg-charcoal">
                Explore the collection <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/about" className="inline-flex items-center rounded-full border border-charcoal/20 px-6 py-3.5 text-sm font-medium text-charcoal transition-colors hover:border-charcoal/50">
                Our story
              </Link>
            </div>
          </div>
          <div className="hidden justify-end md:flex">
            <div className="max-w-[200px] rounded-xl bg-cream/90 p-3 shadow-xl shadow-charcoal/10">
              <span className="relative block aspect-square w-44 overflow-hidden rounded-full border border-[#8c706a]/25 bg-[#eee8e3] shadow-inner">
                <Image src="/images/modest-chic-official-logo.jpeg" alt="Modest Chic by Hira & Muqadas logo" fill sizes="176px" className="object-cover object-[center_16%]" />
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-sand/70 bg-[#564340] text-cream">
        <div className="container-page grid grid-cols-1 divide-y divide-cream/15 py-5 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <div className="flex items-center justify-center gap-3 py-3 text-sm sm:py-1"><Heart className="h-4 w-4 text-[#c8b5ad]" /> Chosen with care</div>
          <div className="flex items-center justify-center gap-3 py-3 text-sm sm:py-1"><PackageCheck className="h-4 w-4 text-[#c8b5ad]" /> Gift-ready details</div>
          <div className="flex items-center justify-center gap-3 py-3 text-sm sm:py-1"><Sparkles className="h-4 w-4 text-[#c8b5ad]" /> Made for everyday elegance</div>
        </div>
      </section>

      <section className="py-20 md:py-28">
        <div className="container-page">
          <div className="mb-10 flex items-end justify-between gap-6 md:mb-14">
            <div>
              <p className="label-text mb-3 text-terracotta">A little inspiration</p>
              <h2 className="heading-lg text-charcoal">Find your kind of lovely</h2>
            </div>
            <Link href="/shop" className="hidden items-center gap-2 pb-1 text-sm font-medium text-charcoal/75 transition-colors hover:text-terracotta sm:flex">
              Shop everything <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {stories.map((story) => (
              <Link key={story.number} href={story.href} className="group rounded-2xl border border-sand/70 bg-[#f4eeea] p-7 transition-all hover:-translate-y-1 hover:border-[#b8a69e] hover:shadow-lg hover:shadow-charcoal/5 md:p-9">
                <span className="font-display text-4xl text-[#80695f]">{story.number}</span>
                <h3 className="mt-8 font-display text-2xl text-charcoal">{story.title}</h3>
                <p className="mt-3 min-h-12 text-sm leading-6 text-charcoal/75">{story.description}</p>
                <span className="mt-7 inline-flex items-center gap-2 text-sm font-medium text-[#564340]">Discover more <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#f7f1ec] py-20 md:py-28">
        <div className="container-page grid items-center gap-12 md:grid-cols-[0.9fr_1.1fr] md:gap-20">
          <div className="relative mx-auto w-full max-w-md overflow-hidden rounded-[44%_44%_18px_18px] bg-[#ebdcd4]">
            <Image src="/images/modest-chic-color-edit.webp" alt="A selection of Modest Chic hijab colors presented with the brand box" width={704} height={1524} className="h-full w-full object-cover" sizes="(max-width: 768px) 90vw, 35vw" />
          </div>
          <div className="max-w-xl">
            <p className="label-text mb-3 text-terracotta">The Modest Chic edit</p>
            <h2 className="heading-lg text-charcoal">A favorite shade for every side of you.</h2>
            <p className="body-base mt-5 text-charcoal/75">
              From gentle neutrals to colors that brighten the day, explore our hijabs and gift sets, thoughtfully brought together by Hira &amp; Muqadas.
            </p>
            <Link href="/shop" className="mt-8 inline-flex items-center gap-3 rounded-full bg-[#564340] px-6 py-3.5 text-sm font-medium text-cream transition-colors hover:bg-charcoal">
              Browse the catalog <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <section className="py-20 md:py-28">
        <div className="container-page">
          <div className="mb-10 flex items-end justify-between gap-6">
            <div>
              <p className="label-text mb-3 text-terracotta">Our edit</p>
              <h2 className="heading-lg text-charcoal">Featured pieces</h2>
            </div>
            <Link href="/shop" className="hidden items-center gap-2 pb-1 text-sm font-medium text-charcoal/75 transition-colors hover:text-terracotta sm:flex">View all <ArrowRight className="h-4 w-4" /></Link>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4 md:gap-6">
            {bestSellers.map((product, index) => <ProductCard key={product.id} product={product} preloadImage={index === 0} />)}
          </div>
        </div>
      </section>

      <section className="relative isolate overflow-hidden bg-[#564340] py-16 text-center text-cream md:py-20">
        <Image src="/images/modest-chic-gift-edit.webp" alt="Modest Chic folded hijab gift set in soft and bright colors" fill className="-z-20 object-cover opacity-20" sizes="100vw" />
        <div className="absolute inset-0 -z-10 bg-[#443431]/75" />
        <div className="container-page">
          <p className="label-text mb-3 text-[#d7c4bc]">A gift that feels personal</p>
          <h2 className="heading-lg mx-auto max-w-2xl text-cream">A lovely little something, for someone lovely.</h2>
          <Link href="/shop?category=sets" className="mt-7 inline-flex items-center gap-3 rounded-full bg-cream px-6 py-3.5 text-sm font-medium text-[#564340] transition-colors hover:bg-[#f0e7e1]">
            Gift sets coming soon <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}

