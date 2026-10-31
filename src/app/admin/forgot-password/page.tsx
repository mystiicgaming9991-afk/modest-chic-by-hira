"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { jsonBody, staffJson } from "@/lib/staff-client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    try { await staffJson("auth/password/forgot", jsonBody({ email })); setDone(true); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed."); }
    finally { setBusy(false); }
  }

  return <section className="mx-auto max-w-md rounded-2xl border border-sand bg-white p-7 shadow-sm">
    <h1 className="heading-md mb-5">Reset staff password</h1>
    {done ? <p>If this account exists, reset instructions will be sent. <Link href="/admin/login" className="text-terracotta underline">Back to sign in</Link></p> : <>
      {error && <p role="alert" className="mb-4 text-rust">{error}</p>}
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        <label className="block text-sm font-medium">Email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <button disabled={busy} className="w-full rounded-lg bg-charcoal p-3 font-medium text-white disabled:opacity-50">{busy ? "Sending…" : "Send reset instructions"}</button>
      </form>
    </>}
  </section>;
}
