# Static storefront

The public website can build its catalogue from Sanity, selected by `catalogue.config.json`. See [Sanity catalogue setup and publishing](SANITY_CATALOGUE.md). The file source in `src/content/catalog.json` remains intentionally empty and is used for local development and deterministic CI. It never imports local database test products. The deployed storefront needs no running API, database, Redis, credentials or continuously running computer. WhatsApp is the order-enquiry channel; availability and all order terms are confirmed in chat.

## Add a product in file mode

For Sanity mode, add and publish products in Studio instead. These steps are for `STOREFRONT_CATALOG_SOURCE=file` builds.

1. Copy actual product photographs into `public/images/products/`. Compress them to WebP before adding them; aim for a few hundred KB rather than camera originals.
2. Copy the object in `docs/product.example.json` into the catalogue's `products` array. The example is documentation only and is not published. Replace every example value with accurate product details and a photo that exists.
3. Use stable unique IDs, SKU codes and lowercase hyphenated slugs. Prices are in PKR, not minor units; optional `salePrice` must not exceed `price`. `stock: 0` makes the variant sold out. This is a published availability snapshot, not a stock reservation.
4. Category and collection slugs must exist in the corresponding catalogue arrays. The catalogue has Hijabs, Accessories and Gift Sets categories, plus New Arrivals and Featured Pieces collections. Add new groups there when needed.
5. Run `npm run catalog:check`, `npm test` and `npm run build:static`.
6. Preview `out/` with a static server. Publish again whenever catalogue data changes. Customers see the last published catalogue; their cart and wishlist stay in that browser only.

## GitHub and Cloudflare Pages

The GitHub repository is `mystiicgaming9991-afk/modest-chic-by-hira`. The package is at the repository root, so leave Cloudflare's root directory blank.

1. Create a **Pages** project in Cloudflare and connect this GitHub repository; select production branch `main`.
2. Select no/custom framework preset. Set build command `npm run build:static` and output directory `out`. `.node-version` pins Node 24 and `wrangler.toml` declares the static output directory.
3. Public build settings are managed by `[vars]` in `wrangler.toml`, which Cloudflare treats as the configuration source of truth. `NEXT_PUBLIC_SITE_URL` is set to `https://modest-chic-by-hira.pages.dev`; update it when connecting a custom domain, then rebuild. The public business number is already configured. GA4 remains disabled until a real Measurement ID is provided.
4. Do not configure a Workers deployment command or a Python backend for this static launch.
5. Source changes pushed to `main` can deploy automatically through Cloudflare's Git integration. GitHub Actions runs catalogue validation, lint, tests and the static build without cloud credentials. These checks do not themselves deploy anything.

## Edit email and Instagram

The Contact page and footer share `src/content/contact.json`:

```json
{
  "email": "modestchic00@gmail.com",
  "instagramHandle": "modestchic.pk"
}
```

Use the public business email and the Instagram username without `@` or a full URL. Set either value to `""` to hide that channel in both locations. Invalid nonempty values fail the build with a `Contact settings:` error. These settings are public; never put passwords or customer details here.

To update through GitHub, open that file, select **Edit**, change the values, and choose **Create a new branch for this commit and start a pull request**. Review the diff and checks before merging into `main`. Cloudflare then builds and deploys the new values automatically; verify the deployment succeeds and check both the Contact page and footer on the live site. A local edit or unmerged pull request does not update production. For local verification, run `npm test`, `npm run lint` and `npm run build:static`.

Email links open the customer's email app with the recipient filled in; they do not send mail automatically. Instagram links open the profile in a new tab; messaging availability depends on the account settings and Instagram sign-in. WhatsApp remains the main ordering channel and appears first in the footer contact list, using `NEXT_PUBLIC_WHATSAPP_NUMBER` and the general enquiry message. If the number is blank or invalid, the footer WhatsApp link is hidden. No backend or paid integration is needed.

## Build and host for free

- Local development: `npm run dev -- -p 3001`. Static data is the default, even if an API is running locally.
- Deployment build: `npm run build:static`. Upload **only `out/`** to Cloudflare Pages or connect a source repository with that command and output directory `out`. Do not use the regular Next.js server preset/build command.
- On Pages configure the project root as `modest-chic` if your repository contains the parent project directory. Use a supported Node version (22.12+, 24.x, or 26+).
- Set `NEXT_PUBLIC_SITE_URL` to the actual HTTPS origin (including `https://`) and rebuild after the first deployment. This makes canonical URLs, sitemap entries, product and photo links usable by customers.
- The public business number defaults to `923144660921`. Override with `NEXT_PUBLIC_WHATSAPP_NUMBER` at build time if it changes.
- `_headers` and `_redirects` are included for Cloudflare Pages. `/checkout` sends customers to `/cart/`; other hosts must configure equivalent rules. There is also a static checkout landing page linking to the cart.
- Product routes are generated only for catalogue products. Unknown slugs return 404. With an empty catalogue, there are no product routes to publish.
- The production storefront is hosted at `https://modest-chic-by-hira.pages.dev`. Running a local build does not publish it; pushes to `main` trigger Cloudflare's deployment.

The build script copies the storefront into ignored `.static-site/`, excludes server/account/admin routes, applies the small `static/app` entrypoints, and builds into `out/`. Shared UI, data types, context interfaces and the Python backend remain in the original source. Do not edit generated files. API development remains available with `COMMERCE_API_URL=http://127.0.0.1:8000 npm run dev:api -- -p 3001`; restoring a hosted backend still requires deploying its services and configuring trusted origins/credentials.

## Optional GA4 analytics

No Google tag, analytics request or tracking consent banner is enabled without a valid `NEXT_PUBLIC_GA_MEASUREMENT_ID`. Do not use a made-up ID in production.

Static browser protections, dependency checks and account setup are documented in [SECURITY.md](SECURITY.md).

1. In Google Analytics create an account/property for Modest Chic, choose the reporting timezone and PKR currency, and create a Web stream for the published storefront URL.
2. Review Google's terms yourself. Copy the stream's public `G-...` Measurement ID.
3. **Turn Enhanced measurement off for this stream** to prevent duplicate navigation/outbound-click events and automatic collection of full WhatsApp URLs, message text or search parameters. Keep Google Signals and advertising features off for this setup.
4. Set `NEXT_PUBLIC_GA_MEASUREMENT_ID` under `[vars]` in `wrangler.toml` for Cloudflare Pages (or in the build environment for another host) and rebuild. This ID is public; never put account credentials in that file.
5. On the website select Allow analytics, then verify events in GA4 Realtime/DebugView. Declining must leave shopping functional and send no GA events. Analytics settings lets visitors change their choice.

Events: `page_view`, `view_item`, `view_cart`, `add_to_cart`, `remove_from_cart`, and `whatsapp_click`. Product events contain public product identifiers, selected variants, quantity, PKR currency and value. Page URLs omit queries; outbound events omit the WhatsApp number, destination URL and prepared message. Free-text searches and customer details are not sent. `?utm_source=instagram` is explicitly recognised as social traffic. Configure the Instagram bio link with that parameter after publishing.

WhatsApp clicks mean enquiries only; do not mark them as purchases. The website cannot know that a message was sent or an order paid. Choose `whatsapp_click` as a lead key event if desired; do not invent purchase events. Analytics remains subject to visitor choice and browser blocking, so reports are not an exact order ledger.
