export const metadata = { title: "Privacy | Modest Chic" };
export default function PrivacyPage() {
  return <article className="container-page max-w-3xl space-y-6 py-16 text-charcoal"><h1 className="heading-lg">Privacy</h1>
    <p>Your cart and wishlist are saved in this browser. They do not create a customer account or reserve stock.</p>
    <p>WhatsApp links open a conversation where you can review and send your request. Customer and delivery details are discussed in WhatsApp under its own privacy practices.</p>
    <p>If Google Analytics is configured, it loads only after you allow analytics. It measures visits, product interactions, cart actions and WhatsApp clicks. We do not intentionally send names, contact details, message text or delivery information to analytics. A WhatsApp click is an enquiry, not a confirmed sale.</p>
    <p>You can change your analytics choice using Analytics settings. If no analytics property is configured, analytics remains disabled.</p>
    <a href="/contact" className="underline">Contact us with a privacy question</a>
  </article>;
}
