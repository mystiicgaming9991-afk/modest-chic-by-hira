import { createHash } from 'node:crypto';

// These headers apply to every response, including unknown routes. Script policy
// lives in each HTML document: Pages limits individual headers to 2,000 chars.
export const staticSecurityHeaders = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  // Host only: do not change HTTPS policy for a client's other subdomains.
  'Strict-Transport-Security': 'max-age=31536000',
  // frame-ancestors is not supported in a meta policy; keep it in the header.
  'Content-Security-Policy': "base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'",
};

export function cloudflareSecurityHeaders() {
  return `/*\n${Object.entries(staticSecurityHeaders).map(([name, value]) => `  ${name}: ${value}`).join('\n')}\n`;
}

export function secureStaticHtml(html, { analyticsEnabled = false } = {}) {
  if (!/<head(?:\s[^>]*)?>/i.test(html)) throw new Error('Cannot apply CSP: HTML head is missing.');
  if (/<meta\b[^>]*http-equiv\s*=\s*["']?Content-Security-Policy\b/i.test(html)) {
    throw new Error('Cannot apply CSP twice to the same HTML document.');
  }
  const hashes = new Set();
  // Next's exported HTML escapes script closing tags inside data. Hash the final
  // script text after HTML newline normalization, exactly as the browser sees it.
  for (const [, attributes, contents] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    if (/(?:^|\s)src\s*=/i.test(attributes)) continue;
    hashes.add(`'sha256-${createHash('sha256').update(contents.replace(/\r\n?/g, '\n')).digest('base64')}'`);
  }
  const analytics = analyticsEnabled ? {
    script: ' https://www.googletagmanager.com',
    image: ' https://*.google-analytics.com https://*.googletagmanager.com',
    connect: ' https://*.google-analytics.com https://*.analytics.google.com https://*.googletagmanager.com',
  } : { script: '', image: '', connect: '' };
  const policy = [
    "default-src 'none'",
    `script-src 'self' ${[...hashes].join(' ')}${analytics.script}`.trim(),
    "script-src-attr 'none'",
    // React uses inline styles for colour swatches and component positioning.
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data:${analytics.image}`,
    "font-src 'self'",
    `connect-src 'self'${analytics.connect}`,
    "manifest-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "form-action 'self'",
  ].join('; ');
  // Insert before any resource/script. A meta policy also protects 404.html when
  // served at arbitrary paths, and scales with catalogue size without route rules.
  const escaped = policy.replaceAll('&', '&amp;').replaceAll('"', '&quot;');
  // Preserve Next's leading charset declaration inside the first 1,024 bytes.
  return html.replace(/<head(?:\s[^>]*)?>(?:\s*<meta\b[^>]*\bcharset\s*=[^>]*>)?/i, (head) => `${head}<meta http-equiv="Content-Security-Policy" content="${escaped}">`);
}
