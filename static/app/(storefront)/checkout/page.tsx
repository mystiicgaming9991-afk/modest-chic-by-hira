import Link from "next/link";
export default function CheckoutPage() {
  return <div className="container-page py-20"><h1 className="heading-md">Order via WhatsApp</h1><p className="my-4">Review your cart and send us your request on WhatsApp.</p><Link className="underline" href="/cart">Go to your cart</Link></div>;
}
