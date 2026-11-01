# Sanity catalogue

The storefront uses Sanity project `k8aco52i`, public dataset `production`, configured in `catalogue.config.json`. The deployed catalogue dashboard is **https://modest-chic-k8aco52i.sanity.studio/**. Sanity Studio is a separate application in `studio/`; it is not the staff order-management backend. The website importer changes remain on a feature branch until reviewed and merged; hosting the Studio does not change the live storefront.

## Daily product updates

1. Sign in to the catalogue Studio with the account that owns the business project.
2. Open **Products → Create**. Enter the name, description, fabric, dimensions and care instructions. Generate the product link once; avoid changing it after sharing it.
3. Select a published category and any published collections. The initial categories are Hijabs, Accessories and Gift Sets; the initial collections are New Arrivals and Featured Pieces. Categories and collections can also be added in Studio. Publish a new group before a product that references it.
4. Upload a real JPG, PNG, WebP, GIF or AVIF photograph, describe it for accessibility, and enter an accurate photo note. The static importer converts the image to WebP at up to 1,400 px wide. Only one primary photo per product is supported by the current storefront.
5. Add each colour/variant: name, six-digit colour hex, globally unique SKU, price in PKR, optional sale price and available quantity. A quantity of zero displays sold out. Keep variant entries and SKUs stable rather than deleting/recreating them when editing a price.
6. Set New, Best seller and homepage Featured flags as appropriate, then **Publish**. Draft saves do not change the storefront. After the deploy hook is activated, a successful Cloudflare build publishes the update automatically. Until then, the website continues to show its previous build.
7. Confirm the Cloudflare deployment succeeds and check the live product page, photo, cart subtotal and WhatsApp preview. Stock is a published snapshot; update it manually after confirmed WhatsApp sales. Publishing does not reserve stock, collect payment or create an order.

Unpublish/delete a product to remove it on the next successful build. Existing cart lines for removed products are retained and visibly unresolved, so the customer must adjust the cart before requesting an order. Never enter supplier costs, customer details, credentials or private notes in this public dataset. Ratings stay zero until a genuine review system exists.

## Local setup and verification

Use the Node version from `.node-version`. Install the storefront with `npm ci` and Studio with `npm ci --prefix studio`. The separate lockfiles keep CMS editing dependencies out of the storefront install.

```sh
npm --prefix studio run login -- --provider github
npm --prefix studio run seed:groups
npm run studio:dev
```

Studio runs at `http://127.0.0.1:3333`. If it requests CORS access, allow this exact local origin for the Studio only. The seed command adds missing groups and existing public brand cover images, never replaces edited groups and never creates products. Run it only for the intended project/dataset.

```sh
npm run test:catalogue
npm run test:static-security
npm test
npm run lint
npm --prefix studio run typecheck
npm run studio:build
NEXT_PUBLIC_SITE_URL=https://modest-chic-by-hira.pages.dev npm run build:static
```

`npm run build:static` reads published content from the uncached Sanity API, downloads optimized images from that project's Sanity CDN, validates the result, and writes a generated snapshot only inside ignored `.static-site/`. Product routes, metadata and sitemap come from that same snapshot. Only `out/` is deployed. Root `src/content/catalog.json` remains the empty local/file-mode source; CMS imports never overwrite or commit it. Regular `npm run dev` uses that local file. Preview CMS changes with a static build and a server serving `out/`.

No Sanity API token is required for public published reads. Browser code has no Sanity client or write token. The storefront serves copied images locally, so its existing CSP does not need additional external origins. Failed queries, invalid products, missing references, failed photos and quota errors stop the build; the importer never silently falls back to demo/old data or drops products. Cloudflare retains the previous successful deployment when a build fails.

For deterministic CI or disconnected development, run `STOREFRONT_CATALOG_SOURCE=file npm run build:static`. This override deliberately builds the file catalogue. Cloudflare production must **not** set that override to `file`. CI tests both the importer with mocked responses and the file build; a live Sanity build is checked separately.

Studio uses narrow dependency overrides for patched CLI transitive dependencies. When upgrading Sanity, run its typecheck, schema validation, build and audit before removing/updating those overrides.

## One-time hosted setup

1. The account currently shows a **$0 Growth Trial** and explicitly states that it will automatically downgrade to **Free** after the trial. The integration uses only Free-plan features; do not upgrade or add paid add-ons. Retain account ownership. Free datasets are public and Free roles are administrator/viewer.
2. The Studio is deployed at `https://modest-chic-k8aco52i.sanity.studio/`. To update its editing fields/interface later, run `npm run deploy` from the authenticated Studio folder. Ordinary product edits do not require Studio deployment. Hosted Studio access still requires Sanity authentication for editing. Do not deploy the Python backend for this flow.
3. Review the website feature branch through a pull request. Merge and complete the first CMS-enabled Cloudflare deployment before enabling automatic product publishing. This integration does not authorize pushing or merging the branch automatically.
4. The Cloudflare hook **Sanity catalogue publish** has been created for branch `main`. Its URL is a secret: never add it to Git, public environment variables or browser code.
5. The Sanity webhook **Cloudflare catalogue publish** is configured for dataset `production`, with create, update and delete enabled and this GROQ filter:

   ```groq
   _type in ["product", "category", "collection"] && !(_id in path("drafts.**")) && !(_id in path("versions.**"))
   ```

6. The Sanity webhook is currently **disabled**. Keep it that way until step 3 is complete. Then enable it, publish a real product and confirm: webhook delivery → successful Cloudflare deployment → product page/cart/WhatsApp details. Do not publish invented test products to the customer's catalogue. The hook redeploys the configured Git branch; it does not bypass GitHub branch protection or merge code.

Sanity currently includes two webhooks on Free; Cloudflare Pages currently includes 500 builds/month and one concurrent Free build. Publish related edits together where possible. Review CMS and build usage; API/bandwidth quota failures can block publication even though the old static storefront remains hosted. No paid add-on is needed for this setup.

## References

- [Sanity Studio hosting](https://www.sanity.io/docs/studio/deployment)
- [Sanity public data and CORS](https://www.sanity.io/docs/content-lake/cors)
- [Sanity API versus API CDN](https://www.sanity.io/docs/content-lake/api-cdn)
- [Cloudflare deploy hooks, including Sanity](https://developers.cloudflare.com/pages/configuration/deploy-hooks/)
- [Sanity plan limits](https://www.sanity.io/pricing)
