"use client";

import { useEffect, useState } from "react";
import { isStaticStorefront } from "@/lib/storefront-mode";
import { useCatalog } from "@/lib/context/catalog-context";

export function PublicPolicy({ type, preview }: { type: "shipping" | "returns"; preview: string }) {
  const { mode } = useCatalog();
  if (isStaticStorefront()) return <p className="body-base text-charcoal/75">{type === "shipping" ? "Please contact us on WhatsApp to confirm delivery coverage, charges and timing before confirming your order." : "Please ask us on WhatsApp about return and exchange terms before confirming your order. Report any issue with your received item in the same conversation."}</p>;
  return <PolicyContent key={`${mode}:${type}`} mode={mode} type={type} preview={preview} />;
}

function PolicyContent({
  mode,
  type,
  preview,
}: {
  mode: "loading" | "preview" | "live" | "error";
  type: "shipping" | "returns";
  preview: string;
}) {
  const [result, setResult] = useState<
    { type: "shipping" | "returns"; content: Record<string, unknown> } |
    { type: "shipping" | "returns"; error: string } |
    null
  >(null);

  useEffect(() => {
    if (mode !== "live") return;
    let active = true;
    fetch(`/api/commerce/policies/${type}`, { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.message ?? "Policy is unavailable.");
        return body as { content: Record<string, unknown> };
      })
      .then((policy) => { if (active) setResult({ type, content: policy.content }); })
      .catch((cause) => {
        if (active) {
          setResult({
            type,
            error: cause instanceof Error ? cause.message : "Policy is unavailable.",
          });
        }
      });
    return () => { active = false; };
  }, [mode, type]);

  const currentResult = result?.type === type ? result : null;
  if (mode === "preview") return <p className="body-base text-charcoal/75">{preview}</p>;
  if (mode === "loading" || mode === "live" && !currentResult) return <p role="status" className="body-base text-charcoal/75">Loading policy…</p>;
  if (currentResult && "error" in currentResult || mode === "error") return <p role="alert" className="body-base text-charcoal/75">{currentResult && "error" in currentResult ? currentResult.error : "Policy is temporarily unavailable."}</p>;
  const content = currentResult && "content" in currentResult ? currentResult.content : {};
  return <div className="space-y-5 text-left">{Object.entries(content).map(([key, value]) => <section key={key}><h2 className="font-medium capitalize text-charcoal">{key.replaceAll("_", " ")}</h2><p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-charcoal/75">{typeof value === "string" ? value : JSON.stringify(value)}</p></section>)}</div>;
}
