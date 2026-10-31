"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useCatalog } from "@/lib/context/catalog-context";

const previewFaqs = [
  { question: "Can I place an order now?", answer: "The collection is currently a storefront preview. You can browse, save pieces, and build a cart, but checkout does not submit orders or take payments yet." },
  { question: "Are the colours product photographs?", answer: "The catalogue currently uses illustrated fabric colour previews. Colour may vary by screen. Product photographs will be added before ordering opens." },
  { question: "What payment and delivery options will be available?", answer: "Payment and delivery details will be confirmed when ordering opens." },
  { question: "How do I care for a hijab?", answer: "Care depends on the fabric. Check the fabric and care details on each product page. Always follow the label on the physical product once available." },
  { question: "What sizes are shown?", answer: "Each product page lists its dimensions so you can compare length and width while browsing." },
  { question: "How can I contact the shop?", answer: "Visit our contact page to chat with us when WhatsApp is available." },
];

const liveFaqs = [
  { question: "Can I place an order now?", answer: "Add items to your cart and send the prepared enquiry on WhatsApp. We will confirm availability and your order in chat." },
  { question: "How do I check my order?", answer: "Please ask us for an update in your WhatsApp conversation." },
  { question: "What payment methods are available?", answer: "We will discuss available payment methods and delivery charges with you on WhatsApp." },
  { question: "How do I care for a hijab?", answer: "See the care details on each product page and follow the label on the physical product." },
  { question: "Where can I find shipping and return terms?", answer: "Read the Shipping and Returns pages and ask us about the terms in your WhatsApp conversation." },
];

export default function FAQPage() {
  const { mode } = useCatalog();
  const faqs = mode === "live" ? liveFaqs : previewFaqs;
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  return (
    <div className="min-h-[65vh] bg-cream">
      <div className="border-b border-sand/50 bg-warm-cream">
        <div className="container-page py-14 text-center">
          <p className="label-text mb-3 text-terracotta">Help</p>
          <h1 className="heading-xl mb-4 text-charcoal">Frequently asked questions</h1>
          <p className="body-lg mx-auto max-w-lg text-charcoal/75">A quick guide to shopping with Modest Chic.</p>
        </div>
      </div>
      <div className="container-page mx-auto max-w-3xl space-y-3 py-14">
        {faqs.map((faq, index) => (
          <div key={faq.question} className="overflow-hidden rounded-xl border border-sand/70 bg-white">
            <button type="button" onClick={() => setOpenIndex(openIndex === index ? null : index)} aria-expanded={openIndex === index} aria-controls={`faq-answer-${index}`} className="flex w-full items-center justify-between gap-4 p-5 text-left text-sm font-medium text-charcoal">
              {faq.question}<ChevronDown className={`h-4 w-4 shrink-0 text-terracotta transition-transform ${openIndex === index ? "rotate-180" : ""}`} />
            </button>
            {openIndex === index && <p id={`faq-answer-${index}`} className="border-t border-sand/50 px-5 py-4 text-sm leading-relaxed text-charcoal/75">{faq.answer}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
