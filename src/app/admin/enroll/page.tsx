"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

export default function EnrollPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loadingIdentity, setLoadingIdentity] = useState(true);
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    staffJson<StaffIdentity>("auth/me")
      .then((value) => { if (active) setIdentity(value); })
      .catch((cause) => {
        if (!active) return;
        if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
        else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
      })
      .finally(() => { if (active) setLoadingIdentity(false); });
    return () => { active = false; };
  }, [router]);

  async function begin() {
    setBusy(true); setError(null);
    try {
      const setup = await staffJson<{ secret: string }>("auth/setup-totp", { method: "POST" });
      setSecret(setup.secret);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Enrollment could not start."); }
    finally { setBusy(false); }
  }

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      await staffJson<void>("auth/verify-totp", jsonBody({ totp_code: code }));
      setSecret(""); setCode(""); router.replace("/admin");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Code verification failed."); }
    finally { setBusy(false); }
  }

  return <section className="mx-auto max-w-lg rounded-2xl border border-sand bg-white p-7 shadow-sm">
    <h1 className="heading-md mb-3">Set up your authenticator</h1>
    <p className="mb-5 text-sm text-charcoal/75">Use an authenticator app to add this account, then enter its six-digit code. Staff actions become available after verification.</p>
    {error && <p role="alert" className="mb-4 rounded-lg bg-rust/10 p-3 text-sm text-rust">{error}</p>}
    {loadingIdentity ? <p role="status">Checking staff session…</p> : !identity ? <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="text-terracotta underline">Sign in</Link>}</p> : identity.totp_enabled ? <p>Authenticator is already enabled. <Link href="/admin" className="text-terracotta underline">Go to staff home</Link>.</p> : <>
      {!secret ? <button onClick={() => void begin()} disabled={busy} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? "Preparing…" : "Start setup"}</button> : <>
        <p className="text-sm">Enter this key manually in your authenticator app:</p>
        <code className="my-3 block break-all rounded-lg bg-warm-cream p-4 text-sm" aria-label="Authenticator setup key">{secret}</code>
        <form onSubmit={(event) => void verify(event)} className="space-y-4">
          <label className="block text-sm font-medium">Six-digit code<input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" value={code} onChange={(event) => setCode(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand p-3" /></label>
          <button disabled={busy} className="w-full rounded-lg bg-charcoal p-3 font-medium text-white disabled:opacity-50">{busy ? "Verifying…" : "Verify and continue"}</button>
        </form>
      </>}
    </>}
  </section>;
}
