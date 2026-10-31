import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { AnalyticsControls } from "@/components/analytics/analytics-controls";
import { Providers } from "../providers";

export default function StorefrontLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Providers><Header /><main id="site-main" className="flex-1">{children}</main><Footer /><AnalyticsControls /></Providers>;
}
