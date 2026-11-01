import contactConfig from "@/content/contact.json";

interface ContactLink {
  label: string;
  href: string;
}

export interface ContactChannels {
  email: ContactLink | null;
  instagram: ContactLink | null;
}

export function getContactChannels(config: unknown = contactConfig): ContactChannels {
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    throw new Error("Contact settings: src/content/contact.json must contain an object.");
  }
  const { email, instagramHandle } = config as Record<string, unknown>;
  if (typeof email !== "string" || typeof instagramHandle !== "string") {
    throw new Error('Contact settings: email and instagramHandle must be strings. Use "" to hide a channel.');
  }
  const address = email.trim();
  const handle = instagramHandle.trim();
  // Accept an unquoted mailbox with a dotted domain, not display names, URL
  // queries or mail headers. URI-encode its local part before building mailto.
  const emailPattern = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+$/;
  const mailbox = address.split("@")[0];
  if (address && (address.length > 254 || mailbox.length > 64 || mailbox.startsWith(".") || mailbox.endsWith(".") || mailbox.includes("..") || !emailPattern.test(address))) {
    throw new Error('Contact settings: email must be a valid email address, or "" to hide it.');
  }
  if (handle && (!/^[a-zA-Z0-9._]{1,30}$/.test(handle) || handle.startsWith(".") || handle.endsWith(".") || handle.includes(".."))) {
    throw new Error('Contact settings: instagramHandle must be a username such as "modestchic.pk", without @ or a URL, or "" to hide it.');
  }
  return {
    email: address ? { label: address, href: `mailto:${encodeURIComponent(address).replace("%40", "@")}` } : null,
    instagram: handle ? { label: `@${handle}`, href: `https://www.instagram.com/${handle}/` } : null,
  };
}
