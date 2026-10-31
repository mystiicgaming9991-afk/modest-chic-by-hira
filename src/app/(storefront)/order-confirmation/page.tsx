import type { Metadata } from "next";
import { Suspense } from "react";
import { ConfirmationClient } from "./confirmation-client";

export const metadata: Metadata = { robots: { index: false, follow: false } };

async function ConfirmationContent({ searchParams }: {
  searchParams: Promise<{ order?: string | string[] }>;
}) {
  const params = await searchParams;
  const orderId = typeof params.order === "string" && /^[0-9a-f-]{36}$/.test(params.order)
    ? params.order : null;
  return <ConfirmationClient orderId={orderId} />;
}

export default function OrderConfirmationPage({ searchParams }: {
  searchParams: Promise<{ order?: string | string[] }>;
}) {
  return <Suspense fallback={<div className="container-page py-20">Loading order…</div>}>
    <ConfirmationContent searchParams={searchParams} />
  </Suspense>;
}
