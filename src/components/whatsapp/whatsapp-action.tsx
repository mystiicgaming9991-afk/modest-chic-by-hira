"use client";

import { useId, useState, useSyncExternalStore } from "react";
import { whatsappLink, whatsappNumber } from "@/lib/whatsapp";

const MAX_LINK_LENGTH = 1800;
const subscribe = () => () => {};
const browserOrigin = () => window.location.origin;
const serverOrigin = () => "";

export function WhatsAppAction({ label, message, disabled = false }: {
  label: string;
  message: (origin: string) => string;
  disabled?: boolean;
}) {
  const [showCopyMessage, setShowCopyMessage] = useState(false);
  const messageId = useId();
  const origin = useSyncExternalStore(subscribe, browserOrigin, serverOrigin);
  const [copyStatus, setCopyStatus] = useState("");
  const number = whatsappNumber(process.env.NEXT_PUBLIC_WHATSAPP_NUMBER);

  if (!number) return <p role="status" className="text-sm text-charcoal/75">WhatsApp contact is currently unavailable.</p>;

  const text = message(origin);
  const url = whatsappLink(number, text);
  const isLong = url.length > MAX_LINK_LENGTH;
  const buttonClass = "inline-flex w-full items-center justify-center rounded-xl bg-charcoal px-6 py-4 text-sm font-medium text-cream hover:bg-ink";

  return <div className="space-y-3">
    {disabled || !origin ? <button type="button" disabled className={`${buttonClass} opacity-50`}>{label}</button> :
      <a href={isLong ? whatsappLink(number) : url} className={buttonClass} onClick={(event) => {
        if (isLong) { event.preventDefault(); setShowCopyMessage(true); }
      }}>{label}</a>}
    {!disabled && origin && !showCopyMessage && <details className="text-sm text-charcoal/75">
      <summary className="cursor-pointer underline">Preview WhatsApp message</summary>
      <p className="mt-3 whitespace-pre-wrap break-words rounded-xl bg-warm-cream p-4">{text}</p>
      <p className="mt-2">Photo links are included when available. Review and send this message in WhatsApp.</p>
    </details>}
    {showCopyMessage && !disabled && <div className="space-y-3 text-sm text-charcoal">
      <p>Your message is too long to open automatically. Copy the complete message, then open WhatsApp and paste it into the chat.</p>
      <label htmlFor={messageId} className="font-medium">Complete message</label>
      <textarea id={messageId} readOnly value={text} rows={8} onFocus={(event) => event.currentTarget.select()} className="w-full rounded-xl border border-sand p-3" />
      <button type="button" className="underline" onClick={async () => {
        try { await navigator.clipboard.writeText(text); setCopyStatus("Copied."); }
        catch { setCopyStatus("Select and copy the message above."); }
      }}>Copy message</button>{" "}
      <a href={whatsappLink(number)} className="underline">Open WhatsApp</a>
      <p role="status">{copyStatus}</p>
    </div>}
  </div>;
}
