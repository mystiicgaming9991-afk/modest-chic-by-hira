import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { test } from 'node:test';
import { cloudflareSecurityHeaders, secureStaticHtml } from './static-security.mjs';

const hash = (text) => `'sha256-${createHash('sha256').update(text).digest('base64')}'`;
const policy = (html) => html.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)[1];

test('permits the exact exported hydration scripts, not changed or injected scripts', () => {
  const script = 'self.__next_f.push([1,"Rose & Gold"]);';
  const html = `<html><head><script src="/_next/static/app.js"></script></head><body><script>${script}</script><script>${script}</script></body></html>`;
  const result = secureStaticHtml(html);
  const csp = policy(result);
  assert.equal(csp.split(hash(script)).length - 1, 1);
  assert.ok(!csp.includes(hash(`${script}alert(1)`)));
  assert.ok(!csp.includes(hash('alert(1)')));
  assert.match(csp, /script-src-attr 'none'/);
  assert.match(csp, /form-action 'self'/);
  const scripts = csp.split('; ').find((directive) => directive.startsWith('script-src '));
  assert.ok(!scripts.includes('unsafe-inline'));
  assert.ok(!scripts.includes('unsafe-eval'));
  assert.ok(!csp.includes('google'));
  assert.ok(result.indexOf('http-equiv=') < result.indexOf('<script'));
  assert.ok(result.endsWith(`<script>${script}</script><script>${script}</script></body></html>`));
});

test('normalizes CRLF before hashing and ignores external script bodies', () => {
  const csp = policy(secureStaticHtml('<html><head></head><body><script>a\r\nb\rc</script><script src="/app.js">ignored</script></body></html>'));
  assert.ok(csp.includes(hash('a\nb\nc')));
  assert.ok(!csp.includes(hash('ignored')));
});

test('keeps the charset before the policy and the policy before any resource', () => {
  const html = secureStaticHtml('<html><head><meta charSet="utf-8"/><link rel="stylesheet" href="/app.css"/></head><body></body></html>');
  assert.ok(html.indexOf('charSet=') < html.indexOf('http-equiv='));
  assert.ok(html.indexOf('http-equiv=') < html.indexOf('<link'));
});

test('allows only the required Google hosts when analytics is configured', () => {
  const csp = policy(secureStaticHtml('<html><head></head></html>', { analyticsEnabled: true }));
  assert.match(csp, /script-src 'self'\s+https:\/\/www.googletagmanager.com/);
  assert.ok(csp.includes('https://*.google-analytics.com'));
  assert.ok(csp.includes('https://*.analytics.google.com'));
  assert.ok(!csp.includes('https:;'));
});

test('fails rather than shipping HTML without a policy or applying it twice', () => {
  assert.throws(() => secureStaticHtml('<html><body>No head</body></html>'), /head is missing/);
  const html = secureStaticHtml('<html><head></head></html>');
  assert.throws(() => secureStaticHtml(html), /twice/);
});

test('protects all routes without claiming a client domain or exceeding Pages limits', () => {
  const headers = cloudflareSecurityHeaders();
  assert.match(headers, /^\/\*\n/);
  assert.match(headers, /frame-ancestors 'none'/);
  assert.match(headers, /Strict-Transport-Security: max-age=31536000\n/);
  assert.ok(!headers.includes('includeSubDomains'));
  assert.ok(!headers.includes('preload'));
  for (const line of headers.split('\n')) assert.ok(line.length < 2000);
});
