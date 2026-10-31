import Link from "next/link";
import { ArrowRight, RotateCcw } from "lucide-react";
import { PublicPolicy } from "@/components/ui/public-policy";

export default function ReturnsPage() {
  return <div className="min-h-[65vh] bg-cream">
    <div className="border-b border-sand/50 bg-warm-cream"><div className="container-page py-14 text-center"><p className="label-text mb-3 text-terracotta">Policy</p><h1 className="heading-xl mb-4 text-charcoal">Returns &amp; exchanges</h1><p className="body-lg mx-auto max-w-lg text-charcoal/75">Clear terms before you buy.</p></div></div>
    <div className="container-page py-16"><div className="mx-auto max-w-2xl rounded-3xl border border-sand bg-white p-8 md:p-12"><RotateCcw className="mx-auto mb-5 h-9 w-9 text-terracotta" /><PublicPolicy type="returns" preview="The return and exchange policy will be published before orders open." /><Link href="/shop" className="mt-7 inline-flex items-center gap-2 rounded-full bg-charcoal px-6 py-3 text-sm font-medium text-cream hover:bg-deep-rust">Browse the collection <ArrowRight className="h-4 w-4" /></Link></div></div>
  </div>;
}
