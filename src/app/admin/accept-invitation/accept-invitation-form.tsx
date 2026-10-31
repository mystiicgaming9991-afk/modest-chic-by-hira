"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { jsonBody, staffJson } from "@/lib/staff-client";

export function AcceptInvitationForm({ token }: { token: string }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmation) { setError("Passwords do not match."); return; }
    setBusy(true); setError(null);
    try {
      await staffJson<void>("auth/accept-invitation", jsonBody({ token, password, display_name: name }));
      setDone(true); setPassword(""); setConfirmation("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Invitation could not be accepted."); }
    finally { setBusy(false); }
  }

  return <section className="mx-auto max-w-md rounded-2xl border border-sand bg-white p-7 shadow-sm">
    <h1 className="heading-md mb-5">Accept staff invitation</h1>
    {!token && <p role="alert" className="text-rust">This invitation link is missing its token.</p>}
    {done ? <p>Account activated. <Link href="/admin/login" className="text-terracotta underline">Sign in</Link> to continue.</p> : <>
      {error && <p role="alert" className="mb-4 rounded-lg bg-rust/10 p-3 text-sm text-rust">{error}</p>}
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        <label className="block text-sm font-medium">Name<input required value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="block text-sm font-medium">Password<input required type="password" minLength={12} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /><span className="mt-1 block text-xs font-normal text-charcoal/75">At least 12 characters; at most 72 UTF-8 bytes.</span></label>
        <label className="block text-sm font-medium">Confirm password<input required type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <button disabled={busy || !token} className="w-full rounded-lg bg-charcoal p-3 font-medium text-white disabled:opacity-50">{busy ? "Activating…" : "Activate account"}</button>
      </form>
    </>}
  </section>;
}
