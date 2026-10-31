import Link from "next/link";
import { contactEnquiry, whatsappLink, whatsappNumber } from "@/lib/whatsapp";
import { ArrowRight, MessageCircle } from "lucide-react";

export default function ContactPage() {
  const number = whatsappNumber(process.env.NEXT_PUBLIC_WHATSAPP_NUMBER);
  return (
    <div className="min-h-[60vh] bg-cream">
      <div className="border-b border-sand/50 bg-warm-cream">
        <div className="container-page py-14 text-center md:py-18">
          <p className="label-text mb-3 text-terracotta">Get in touch</p>
          <h1 className="heading-xl mb-4 text-charcoal">Contact us</h1>
          <p className="body-lg mx-auto max-w-lg text-charcoal/75">We would love to hear from you.</p>
        </div>
      </div>
      <div className="container-page py-14 md:py-20">
        <div className="mx-auto max-w-2xl rounded-3xl border border-sand bg-white p-8 text-center shadow-sm md:p-12">
          <span className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-warm-cream text-terracotta"><MessageCircle className="h-7 w-7" /></span>
          <h2 className="heading-sm mb-3 text-charcoal">Chat with us</h2>
          <p className="body-base mx-auto mb-7 max-w-lg text-charcoal/75">Send us a message on WhatsApp and we will be happy to help.</p>
          {number ? <a href={whatsappLink(number, contactEnquiry())} className="inline-flex w-full items-center justify-center rounded-xl bg-charcoal px-6 py-4 text-sm font-medium text-cream hover:bg-ink">Chat on WhatsApp</a> : <p role="status" className="text-sm text-charcoal/75">WhatsApp contact is currently unavailable.</p>}
          <Link href="/shop" className="mt-4 inline-flex items-center gap-2 rounded-full bg-charcoal px-6 py-3 text-sm font-medium text-cream transition-colors hover:bg-deep-rust">Browse the collection <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </div>
    </div>
  );
}
