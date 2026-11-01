import Link from "next/link";
import { contactEnquiry, whatsappLink, whatsappNumber } from "@/lib/whatsapp";
import { getContactChannels } from "@/lib/contact";
import { ArrowRight, Camera, Mail, MessageCircle } from "lucide-react";

export default function ContactPage() {
  const number = whatsappNumber(process.env.NEXT_PUBLIC_WHATSAPP_NUMBER);
  const { email, instagram } = getContactChannels();
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
        {(email || instagram) && (
          <div className={`mx-auto mt-6 grid max-w-2xl gap-6 ${email && instagram ? "md:grid-cols-2" : ""}`}>
            {email && (
              <section aria-labelledby="contact-email-heading" className="flex min-w-0 flex-col rounded-3xl border border-sand bg-white p-7 shadow-sm">
                <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-warm-cream text-terracotta"><Mail aria-hidden="true" className="h-5 w-5" /></span>
                <h2 id="contact-email-heading" className="heading-sm mb-3 text-charcoal">Email us</h2>
                <p className="body-sm mb-6 text-charcoal/75">For questions about our collection or an existing order.</p>
                <a href={email.href} className="mt-auto w-fit max-w-full break-all rounded text-sm font-medium text-charcoal underline decoration-terracotta/50 underline-offset-4 hover:text-deep-rust focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-terracotta">{email.label}</a>
              </section>
            )}
            {instagram && (
              <section aria-labelledby="contact-instagram-heading" className="flex min-w-0 flex-col rounded-3xl border border-sand bg-white p-7 shadow-sm">
                <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-warm-cream text-terracotta"><Camera aria-hidden="true" className="h-5 w-5" /></span>
                <h2 id="contact-instagram-heading" className="heading-sm mb-3 text-charcoal">Find us on Instagram</h2>
                <p className="body-sm mb-6 text-charcoal/75">Visit our profile for updates and enquiries.</p>
                <a href={instagram.href} target="_blank" rel="noopener noreferrer" className="mt-auto w-fit max-w-full break-all rounded text-sm font-medium text-charcoal underline decoration-terracotta/50 underline-offset-4 hover:text-deep-rust focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-terracotta">{instagram.label}<span className="sr-only"> (opens in a new tab)</span></a>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
