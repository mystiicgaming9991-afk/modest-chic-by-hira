import { ResetPasswordForm } from "./reset-password-form";
import { Suspense } from "react";

async function ResetContent({ searchParams }: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token = "" } = await searchParams;
  return <ResetPasswordForm token={token} />;
}

export default function ResetPasswordPage({ searchParams }: {
  searchParams: Promise<{ token?: string }>;
}) {
  return <Suspense fallback={<p>Loading reset form…</p>}><ResetContent searchParams={searchParams} /></Suspense>;
}
