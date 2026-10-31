# Static storefront

The public website uses an empty, real-product catalogue in `src/content/catalog.json`. It never imports local database test products. It needs no API, database, Redis, credentials or continuously running computer. WhatsApp is the order-enquiry channel; availability and all order terms are confirmed in chat.

## Add a product

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
3. Set `NEXT_PUBLIC_SITE_URL` to the actual published HTTPS origin once available, then rebuild. The public business number is already configured. GA4 remains disabled until a real Measurement ID is provided.
4. Do not configure a Workers deployment command or a Python backend for this static launch.
5. Source changes pushed to `main` can deploy automatically through Cloudflare's Git integration. GitHub Actions runs catalogue validation, lint, tests and the static build without cloud credentials. These checks do not themselves deploy anything.

## Build and host for free

- Local development: `npm run dev -- -p 3001`. Static data is the default, even if an API is running locally.
- Deployment build: `npm run build:static`. Upload **only `out/`** to Cloudflare Pages or connect a source repository with that command and output directory `out`. Do not use the regular Next.js server preset/build command.
- On Pages configure the project root as `modest-chic` if your repository contains the parent project directory. Use a supported Node version (22.12+, 24.x, or 26+).
- Set `NEXT_PUBLIC_SITE_URL` to the actual HTTPS origin (including `https://`) and rebuild after the first deployment. This makes canonical URLs, sitemap entries, product and photo links usable by customers.
- The public business number defaults to `923144660921`. Override with `NEXT_PUBLIC_WHATSAPP_NUMBER` at build time if it changes.
- `_headers` and `_redirects` are included for Cloudflare Pages. `/checkout` sends customers to `/cart/`; other hosts must configure equivalent rules. There is also a static checkout landing page linking to the cart.
- Product routes are generated only for catalogue products. Unknown slugs return 404. With an empty catalogue, there are no product routes to publish.
- No registration, cloud account or production deployment has been performed by this local build.

The build script copies the storefront into ignored `.static-site/`, excludes server/account/admin routes, applies the small `static/app` entrypoints, and builds into `out/`. Shared UI, data types, context interfaces and the Python backend remain in the original source. Do not edit generated files. API development remains available with `COMMERCE_API_URL=http://127.0.0.1:8000 npm run dev:api -- -p 3001`; restoring a hosted backend still requires deploying its services and configuring trusted origins/credentials.

## Optional GA4 analytics

No Google tag, analytics request or tracking consent banner is enabled without a valid `NEXT_PUBLIC_GA_MEASUREMENT_ID`. Do not use a made-up ID in production.

1. In Google Analytics create an account/property for Modest Chic, choose the reporting timezone and PKR currency, and create a Web stream for the published storefront URL.
2. Review Google's terms yourself. Copy the stream's public `G-...` Measurement ID.
3. **Turn Enhanced measurement off for this stream** to prevent duplicate navigation/outbound-click events and automatic collection of full WhatsApp URLs, message text or search parameters. Keep Google Signals and advertising features off for this setup.
4. Set `NEXT_PUBLIC_GA_MEASUREMENT_ID` in the hosting build environment and rebuild.
5. On the website select Allow analytics, then verify events in GA4 Realtime/DebugView. Declining must leave shopping functional and send no GA events. Analytics settings lets visitors change their choice.

Events: `page_view`, `view_item`, `view_cart`, `add_to_cart`, `remove_from_cart`, and `whatsapp_click`. Product events contain public product identifiers, selected variants, quantity, PKR currency and value. Page URLs omit queries; outbound events omit the WhatsApp number, destination URL and prepared message. Free-text searches and customer details are not sent. `?utm_source=instagram` is explicitly recognised as social traffic. Configure the Instagram bio link with that parameter after publishing.

WhatsApp clicks mean enquiries only; do not mark them as purchases. The website cannot know that a message was sent or an order paid. Choose `whatsapp_click` as a lead key event if desired; do not invent purchase events. Analytics remains subject to visitor choice and browser blocking, so reports are not an exact order ledger.
