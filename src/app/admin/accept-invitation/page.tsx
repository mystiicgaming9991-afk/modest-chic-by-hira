import { AcceptInvitationForm } from "./accept-invitation-form";
import { Suspense } from "react";

async function InvitationContent({ searchParams }: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token = "" } = await searchParams;
  return <AcceptInvitationForm token={token} />;
}

export default function AcceptInvitationPage({ searchParams }: {
  searchParams: Promise<{ token?: string }>;
}) {
  return <Suspense fallback={<p>Loading invitation…</p>}><InvitationContent searchParams={searchParams} /></Suspense>;
}
