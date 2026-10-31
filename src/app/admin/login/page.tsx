"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { jsonBody, staffJson } from "@/lib/staff-client";

export default function StaffLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const session = await staffJson<{ auth_state: string }>("auth/login", jsonBody({ email, password, totp_code: totpCode || null }));
      router.replace(session.auth_state === "TOTP_ENROLLMENT_REQUIRED" ? "/admin/enroll" : "/admin");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign in failed.");
    } finally { setBusy(false); }
  }

  return <section className="mx-auto max-w-md rounded-2xl border border-sand bg-white p-7 shadow-sm">
    <h1 className="heading-md mb-2">Staff sign in</h1>
    <p className="mb-6 text-sm text-charcoal/75">Use your invited staff account.</p>
    {error && <p role="alert" className="mb-4 rounded-lg bg-rust/10 p-3 text-sm text-rust">{error}</p>}
    <form onSubmit={(event) => void submit(event)} className="space-y-4">
      <label className="block text-sm font-medium">Email<input type="email" required autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <label className="block text-sm font-medium">Password<input type="password" required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <label className="block text-sm font-medium">Authenticator code <span className="font-normal text-charcoal/75">(if enrolled)</span><input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" value={totpCode} onChange={(event) => setTotpCode(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
      <button type="submit" disabled={busy} className="w-full rounded-lg bg-charcoal p-3 font-medium text-white disabled:opacity-50">{busy ? "Signing in…" : "Sign in"}</button>
    </form>
    <Link href="/admin/forgot-password" className="mt-5 inline-block text-sm text-terracotta hover:underline">Forgot password?</Link>
  </section>;
}
