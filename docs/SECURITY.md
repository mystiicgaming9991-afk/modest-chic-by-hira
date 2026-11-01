# Static storefront security

The public storefront contains no customer login, payment processing, order API or database. Customers send requests themselves through WhatsApp. The retained backend needs a separate security review before deployment.

## Protections in the static build

`npm run build:static` adds these protections to `out/`:

- A Content Security Policy in the beginning of every exported HTML head, including the 404 pages. Only the exact build-generated inline scripts are allowed by SHA-256 hashes. Scripts from the same origin are allowed; arbitrary inline scripts, inline event handlers and `eval()` are blocked. Hashes are regenerated with every build.
- Local images, fonts, CSS, network requests and same-origin form submissions (including catalogue search) are allowed. Inline **styles** remain allowed for React positioning and colour swatches. Google Analytics hosts are allowed only when a valid public GA4 Measurement ID is supplied; the existing consent requirement still applies. Other external scripts, frames, plugins, media and cross-origin form submissions are blocked.
- The HTTP CSP header blocks embedding with `frame-ancestors 'none'`; this directive cannot be enforced by a meta tag. The per-page script policy uses HTML instead of route-specific headers to stay within Cloudflare Pages' 2,000-character header and 100-rule limits as the catalogue grows.
- HSTS tells browsers to use HTTPS for one year after a secure visit. It intentionally omits `includeSubDomains` and `preload` so it does not change policy for other client services. HSTS is ignored by browsers on a local HTTP preview.
- Existing MIME-sniffing, frame, referrer and browser-permission headers remain enabled through Cloudflare's `_headers` file.

Serve only `out/`. Ordinary Python/static development servers ignore `_headers`; verify response headers on a Cloudflare preview before merging. The CSP meta policy still works with an ordinary static server. `next dev` and the future API deployment do not use these static-only policies.

Cloudflare HTML/script rewriting (for example, Rocket Loader or automatic analytics injection) can invalidate script hashes or introduce blocked scripts. Keep those features off unless their interaction with the policy is deliberately tested. Do not resolve a CSP error by enabling `unsafe-inline` or `unsafe-eval` for scripts.

Run `npm run test:static-security`, `npm test`, `npm run lint`, `npm audit --omit=dev --audit-level=high` and `npm run build:static`. Check initial page loads, client navigation, search/menu controls, cart, WhatsApp previews and the 404 page. The production dependency audit is a known-vulnerability check, not a full penetration test.

## GitHub and account protection

- Dependabot alerts and automatic security-update pull requests can be enabled independently of deploying code. Secret scanning and push protection should remain enabled.
- `.github/dependabot.yml` proposes weekly npm and GitHub Actions updates after the file reaches the default branch. Updates open pull requests; they are not automatically merged. The retained backend is outside this version-update configuration.
- The storefront workflow validates the catalogue, runs tests/lint and the static build, and fails on known high/critical production npm vulnerabilities.
- Work on feature branches and merge through pull requests. Cloudflare deploys `main` automatically; a local branch does not change production. Account-level branch protection currently requires a pull request, enforces the restriction for administrators, blocks force pushes/deletions and requires conversations to be resolved. It does not require a second person's approval, so the sole maintainer can merge. Required CI status checks can be added after the workflow's check name is verified on a pull request; they are not currently enforced by branch protection.

The account owners must set up two-factor authentication themselves for GitHub, Cloudflare and WhatsApp. Keep recovery codes in their password manager. Invite collaborators with individual accounts, and remove access when the project ends. Never commit credentials, customer conversations or delivery details to this public repository.

Cloudflare Pages provides the hosting TLS/network protections. Custom WAF rules for an owned domain are separate from the current `pages.dev` address. No paid service, CAPTCHA, new tracking service or backend is required by this change.
