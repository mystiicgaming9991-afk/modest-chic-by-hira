"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { jsonBody, staffJson } from "@/lib/staff-client";

export function ResetPasswordForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmation) { setError("Passwords do not match."); return; }
    setBusy(true); setError(null);
    try { await staffJson<void>("auth/password/reset", jsonBody({ token, new_password: password })); setDone(true); setPassword(""); setConfirmation(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Password could not be reset."); }
    finally { setBusy(false); }
  }

  return <section className="mx-auto max-w-md rounded-2xl border border-sand bg-white p-7 shadow-sm">
    <h1 className="heading-md mb-5">Choose a new password</h1>
    {!token && <p role="alert" className="text-rust">This reset link is missing its token.</p>}
    {done ? <p>Password updated. <Link href="/admin/login" className="text-terracotta underline">Sign in</Link> with the new password.</p> : <>
      {error && <p role="alert" className="mb-4 text-rust">{error}</p>}
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        <label className="block text-sm font-medium">New password<input required type="password" minLength={12} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <label className="block text-sm font-medium">Confirm password<input required type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
        <button disabled={busy || !token} className="w-full rounded-lg bg-charcoal p-3 font-medium text-white disabled:opacity-50">{busy ? "Updating…" : "Update password"}</button>
      </form>
    </>}
  </section>;
}
