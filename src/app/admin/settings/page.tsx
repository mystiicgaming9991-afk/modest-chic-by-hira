"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { jsonBody, staffJson, type StaffIdentity } from "@/lib/staff-client";
import { isUnauthorizedStaffError } from "@/lib/staff-session";

type SettingKind = "boolean" | "integer" | "object" | "secret";
interface SettingDefinition { key: string; label: string; description: string; kind: SettingKind }
interface StoreSetting { key: string; value: unknown; is_secret: boolean; version: number; updated_at: string; updated_by: string | null }
interface SettingList { items: StoreSetting[] }
interface PolicyVersion { id: string; type: string; version: number; effective_from: string; content: Record<string, unknown>; approved_by: string | null; created_at: string }
interface PolicyList { items: PolicyVersion[] }

const SETTING_DEFINITIONS: SettingDefinition[] = [
  { key: "fulfillment.availability", label: "Fulfillment availability", description: "Delivery and pickup enablement and approved service cities.", kind: "object" },
  { key: "operational.quote_timeout_seconds", label: "Quote timeout", description: "Seconds before a manual quote expires.", kind: "integer" },
  { key: "operational.order_lock_timeout_seconds", label: "Order lock timeout", description: "Seconds before a cart reservation lock expires.", kind: "integer" },
  { key: "provider.resend_api_key", label: "Resend API key", description: "Encrypted transactional email provider secret.", kind: "secret" },
  { key: "checkout.guest_allowed", label: "Guest checkout", description: "Allow guest checkout when approved policy versions are active.", kind: "boolean" },
  { key: "checkout.cod_allowed", label: "Cash on delivery", description: "Offer COD after the confirmation workflow is available.", kind: "boolean" },
  { key: "checkout.online_payment_allowed", label: "Online payment", description: "Online payment remains unavailable until provider callbacks are configured.", kind: "boolean" },
  { key: "checkout.delivery_fee_minor", label: "Delivery fee", description: "Approved flat fee in PKR paisa (minor units).", kind: "integer" },
  { key: "pickup.available", label: "Pickup availability", description: "Pickup requires approved location and operating terms.", kind: "boolean" },
  { key: "returns.window_days", label: "Return window", description: "Approved return window in days.", kind: "integer" },
];
const POLICY_TYPES = ["checkout_bundle", "returns", "shipping", "privacy", "terms", "cod_confirmation"];
const EMPTY_CONTENT = "{\n  \n}";

export default function StoreSettingsPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<StaffIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState<StoreSetting[]>([]);
  const [selectedKey, setSelectedKey] = useState(SETTING_DEFINITIONS[0].key);
  const selectedKeyRef = useRef(selectedKey);
  const [settingValue, setSettingValue] = useState("");
  const [policyType, setPolicyType] = useState("shipping");
  const policyTypeRef = useRef(policyType);
  const policyRequestRef = useRef(0);
  const [policies, setPolicies] = useState<PolicyVersion[]>([]);
  const [policyContent, setPolicyContent] = useState(EMPTY_CONTENT);
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedDefinition = useMemo(
    () => SETTING_DEFINITIONS.find((definition) => definition.key === selectedKey) ?? SETTING_DEFINITIONS[0],
    [selectedKey],
  );
  const currentSetting = settings.find((setting) => setting.key === selectedKey);

  const loadSettings = useCallback(async () => {
    setError(null);
    try {
      const result = await staffJson<SettingList>("admin/settings");
      setSettings(result.items);
      const key = selectedKeyRef.current;
      const definition = SETTING_DEFINITIONS.find((item) => item.key === key) ?? SETTING_DEFINITIONS[0];
      setSettingValue(settingInputValue(definition, result.items.find((setting) => setting.key === key)));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Store settings could not be loaded."); }
  }, []);

  const loadPolicies = useCallback(async (type: string) => {
    if (!identity?.permission_keys.includes("settings.manage")) return;
    const requestId = ++policyRequestRef.current;
    try {
      const result = await staffJson<PolicyList>(`admin/policies?type=${encodeURIComponent(type)}`);
      if (policyRequestRef.current === requestId && policyTypeRef.current === type) setPolicies(result.items);
    } catch (cause) {
      if (policyRequestRef.current === requestId && policyTypeRef.current === type) {
        setError(cause instanceof Error ? cause.message : "Policy versions could not be loaded.");
      }
    }
  }, [identity]);

  function selectSetting(key: string) {
    selectedKeyRef.current = key;
    setSelectedKey(key);
    const definition = SETTING_DEFINITIONS.find((item) => item.key === key) ?? SETTING_DEFINITIONS[0];
    setSettingValue(settingInputValue(definition, settings.find((setting) => setting.key === key)));
  }

  function selectPolicyType(type: string) {
    policyTypeRef.current = type;
    setPolicyType(type);
    setPolicies([]);
  }

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void staffJson<StaffIdentity>("auth/me").then((user) => {
        if (active) setIdentity(user);
      }).catch((cause) => {
        if (!active) return;
        if (isUnauthorizedStaffError(cause)) router.replace("/admin/login");
        else setError(cause instanceof Error ? cause.message : "Staff access could not be checked.");
      }).finally(() => {
        if (active) setLoading(false);
      });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [router]);

  useEffect(() => {
    if (!identity?.permission_keys.includes("settings.manage")) return;
    const timer = window.setTimeout(() => void loadSettings(), 0);
    return () => window.clearTimeout(timer);
    // Settings are loaded once after the permission check.
  }, [identity, loadSettings]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPolicies(policyType), 0);
    return () => window.clearTimeout(timer);
  }, [policyType, loadPolicies]);

  async function saveSetting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    try {
      let value: unknown = settingValue;
      if (selectedDefinition.kind === "object") value = JSON.parse(settingValue) as unknown;
      if (selectedDefinition.kind === "integer") {
        value = Number(settingValue);
        if (!Number.isSafeInteger(value)) throw new Error("Enter a whole number.");
      }
      if (selectedDefinition.kind === "boolean") value = settingValue === "true";
      if (selectedDefinition.kind === "secret" && !settingValue) throw new Error("Enter a new secret value.");
      const request = selectedDefinition.kind === "secret"
        ? staffJson<StoreSetting>("admin/settings/secrets", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: selectedKey, value, version: currentSetting?.version ?? 1 }),
        })
        : staffJson<StoreSetting>("admin/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: selectedKey, value, version: currentSetting?.version ?? 1 }),
        });
      const updated = await request;
      setSettings((current) => [...current.filter((setting) => setting.key !== selectedKey), updated]);
      if (selectedDefinition.kind === "secret" && selectedKeyRef.current === selectedKey) setSettingValue("");
      setNotice(`${selectedDefinition.label} saved as version ${updated.version}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Setting could not be saved.");
      await loadSettings();
    } finally { setBusy(false); }
  }

  async function publishPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    try {
      const content = JSON.parse(policyContent) as Record<string, unknown>;
      const effective = new Date(effectiveFrom);
      if (!effectiveFrom || Number.isNaN(effective.valueOf())) throw new Error("Choose a valid effective date and time.");
      const policy = await staffJson<PolicyVersion>("admin/policies", jsonBody({
        type: policyType,
        effective_from: effective.toISOString(),
        content,
      }));
      setPolicies((current) => [policy, ...current]);
      setNotice(`${policyType} policy version ${policy.version} published.`);
      setPolicyContent(EMPTY_CONTENT);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Policy version could not be published."); }
    finally { setBusy(false); }
  }

  if (loading) return <p role="status">Checking staff access…</p>;
  if (!identity) return <p role="alert">{error ?? "Staff sign in is required."} {!error && <Link href="/admin/login" className="underline">Sign in</Link>}</p>;
  if (!identity.permission_keys.includes("settings.manage")) return <p role="alert">Store settings are restricted to authorized owners. <Link href="/admin" className="underline">Back to staff home</Link></p>;

  return <div className="space-y-8">
    <header><p className="text-xs uppercase tracking-widest text-terracotta">Owner workspace</p><h1 className="heading-md mt-2">Store settings and policies</h1><p className="mt-2 text-sm text-charcoal/75">Changes are versioned and audited. Business settings only enable flows that have approved terms and operational setup.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rust/10 p-4 text-rust">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-warm-cream p-4">{notice}</p>}
    <section className="grid gap-5 rounded-2xl border border-sand bg-white p-5 lg:grid-cols-[minmax(14rem,0.7fr)_minmax(24rem,1.3fr)]">
      <div className="space-y-3"><div><h2 className="heading-sm">Store rules</h2><p className="mt-1 text-sm text-charcoal/75">Unconfigured values use no implicit approval; dependent flows stay closed.</p></div><ul className="space-y-2">{SETTING_DEFINITIONS.map((definition) => {
        const saved = settings.find((setting) => setting.key === definition.key);
        return <li key={definition.key}><button type="button" disabled={busy} onClick={() => selectSetting(definition.key)} className={`w-full rounded-xl border p-3 text-left disabled:opacity-50 ${selectedKey === definition.key ? "border-terracotta" : "border-sand hover:border-terracotta/60"}`}><span className="flex justify-between gap-2"><strong className="text-sm">{definition.label}</strong><span className="text-xs text-charcoal/75">{saved ? `v${saved.version}` : "Not set"}</span></span><span className="mt-1 block text-xs text-charcoal/75">{definition.key}</span></button></li>;
      })}</ul></div>
      <form onSubmit={(event) => void saveSetting(event)} className="space-y-4 rounded-xl bg-cream/70 p-4">
        <div><h3 className="font-medium">{selectedDefinition.label}</h3><p className="mt-1 text-sm text-charcoal/75">{selectedDefinition.description}</p><p className="mt-2 text-xs text-charcoal/75">{currentSetting ? `Current version ${currentSetting.version} · updated ${new Date(currentSetting.updated_at).toLocaleString()}` : "Not configured · first write uses version 1"}</p></div>
        {selectedDefinition.kind === "boolean" ? <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={settingValue === "true"} disabled={busy || ["checkout.online_payment_allowed", "pickup.available"].includes(selectedKey)} onChange={(event) => setSettingValue(String(event.target.checked))} />Enabled</label>
          : selectedDefinition.kind === "object" ? <label className="block text-sm">JSON value<textarea required rows={8} value={settingValue} disabled={busy} onChange={(event) => setSettingValue(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3 font-mono text-xs" /></label>
            : <label className="block text-sm">{selectedDefinition.kind === "secret" ? "New secret" : selectedDefinition.kind === "integer" ? "Whole number" : "Value"}<input required={selectedDefinition.kind !== "secret" || !currentSetting} type={selectedDefinition.kind === "secret" ? "password" : selectedDefinition.kind === "integer" ? "number" : "text"} min={selectedDefinition.kind === "integer" ? 0 : undefined} value={settingValue} disabled={busy} onChange={(event) => setSettingValue(event.target.value)} placeholder={selectedDefinition.kind === "secret" && currentSetting ? "Leave blank to keep the saved secret" : ""} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3" /></label>}
        {selectedDefinition.kind === "secret" && currentSetting && <p className="text-xs text-charcoal/75">Saved secret: masked. Leaving this field blank keeps the current value.</p>}
        <button disabled={busy || (selectedDefinition.kind === "secret" && !settingValue)} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? "Saving…" : "Save setting"}</button>
      </form>
    </section>
    <section className="grid gap-5 rounded-2xl border border-sand bg-white p-5 lg:grid-cols-[minmax(14rem,0.7fr)_minmax(24rem,1.3fr)]">
      <div className="space-y-3"><div><h2 className="heading-sm">Policy versions</h2><p className="mt-1 text-sm text-charcoal/75">Policy text is immutable after publication. Publish a new version to change it.</p></div><label className="block text-sm">Policy type<select value={policyType} disabled={busy} onChange={(event) => selectPolicyType(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3">{POLICY_TYPES.map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select></label><ul className="space-y-2">{policies.map((policy) => <li key={policy.id} className="rounded-xl border border-sand p-3"><p className="font-medium">Version {policy.version}</p><p className="mt-1 text-xs text-charcoal/75">Effective {new Date(policy.effective_from).toLocaleString()} · {policy.approved_by ? "approved" : "unapproved"}</p></li>)}</ul>{!policies.length && <p className="text-sm text-charcoal/75">No published versions for this type.</p>}</div>
      <form onSubmit={(event) => void publishPolicy(event)} className="space-y-3 rounded-xl bg-cream/70 p-4"><div><h3 className="font-medium">Publish {policyType.replaceAll("_", " ")} version</h3><p className="mt-1 text-sm text-charcoal/75">Enter only approved business content. This action records the current staff member as approver.</p></div><label className="block text-sm">Effective from<input required type="datetime-local" value={effectiveFrom} disabled={busy} onChange={(event) => setEffectiveFrom(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3" /></label><label className="block text-sm">Policy content (JSON)<textarea required rows={10} value={policyContent} disabled={busy} onChange={(event) => setPolicyContent(event.target.value)} className="mt-1 block w-full rounded-lg border border-sand bg-white p-3 font-mono text-xs" /></label><button disabled={busy} className="rounded-lg bg-charcoal px-5 py-3 text-sm font-medium text-white disabled:opacity-50">{busy ? "Publishing…" : "Publish immutable version"}</button></form>
    </section>
    <Link href="/admin" className="inline-block text-sm text-terracotta underline">Back to staff home</Link>
  </div>;
}

function settingInputValue(definition: SettingDefinition, setting?: StoreSetting): string {
  if (definition.kind === "secret") return "";
  if (!setting) return definition.kind === "object" ? "{}" : "";
  return definition.kind === "object"
    ? JSON.stringify(setting.value, null, 2)
    : String(setting.value);
}
