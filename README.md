# Modest Chic

Next.js storefront with a static, WhatsApp-first launch mode and the Python commerce API retained in `backend/`.

## Static launch (current default)

```bash
npm ci
npm run dev -- -p 3001
npm run catalog:check
npm run build:static
```

Publish only `out/` to Cloudflare Pages using `npm run build:static` as the build command. No backend services are required. The real-product catalogue starts empty. Manage products in [Sanity Studio](https://modest-chic-k8aco52i.sanity.studio/); the static build imports published content using `catalogue.config.json`. See [the Sanity catalogue guide](docs/SANITY_CATALOGUE.md) for editing, setup and automatic publishing, and [the static storefront guide](docs/STATIC_STOREFRONT.md) for hosting, optional GA4 setup and the API integration path. GA4 stays disabled without a Measurement ID and visitor consent.

Regular `npm run dev` uses the local file catalogue in `src/content/catalog.json`. To preview Sanity content, run `npm run build:static` and serve `out/` with a static web server. Product edits reach the live site after a successful rebuild; the Publish webhook stays disabled until this feature branch is merged.

The sections below describe the retained API development mode. Use `npm run dev:api` to select it; `npm run dev` uses static catalogue data by default.

## Run locally

Use Node.js 22.12+, 24.x, or 26+ for the storefront and test toolchain.

Start PostgreSQL and Redis, configure the backend, and apply migrations:

```bash
cd backend
uv sync
cp .env.example .env
docker compose up -d postgres redis
uv run alembic upgrade head
uv run uvicorn modest_chic_backend.main:create_app --factory --reload
```

In another terminal, start the storefront:

```bash
npm ci
COMMERCE_API_URL=http://127.0.0.1:8000 npm run dev:api
```

`COMMERCE_API_URL` is server-side only. The browser uses `/api/commerce/*`, which keeps guest and private order credentials in HttpOnly cookies. Without `COMMERCE_API_URL`, catalog pages show sample preview data and ordering is disabled. A configured but unavailable API produces an error instead of sample prices.

Set `NEXT_PUBLIC_SITE_URL` to the public storefront origin in deployed environments (for example, `https://shop.example.com`) so product and collection pages can emit absolute canonical and Open Graph URLs. Catalog-backed titles and descriptions still render without it; absolute URLs are omitted until the origin is configured.

Staff sign-in is at `/admin/login`; authorized staff can work pending COD orders at `/admin/orders/cod`. Backend `TRUSTED_ORIGINS` must include the exact storefront origin for staff mutations. The `/api/staff/*` proxy stores staff access and refresh credentials separately from shopping credentials.

The public WhatsApp Business number defaults to `923144660921` (+92 314 4660921). To change it, set `NEXT_PUBLIC_WHATSAPP_NUMBER` at build time to the new international number, digits only (no plus sign, spaces, or leading zero), then rebuild. An empty or invalid value makes WhatsApp contact unavailable. With a live catalogue, customers can send cart enquiries; confirm availability, pricing, delivery and payment in WhatsApp, then enter confirmed orders in staff admin if desired. The customer must send the message, and the cart is not cleared automatically. The existing checkout backend is retained for future use; `/checkout` currently redirects to the cart.

WhatsApp messages use separate general-enquiry, product-enquiry and cart-request templates. Product messages include the selected shade/SKU, quantity, displayed price and item subtotal. Cart messages include every item and the estimated subtotal. Both include product links and real catalogue photo links when available; placeholder images are omitted. Click-to-chat sends text and links, not image attachments. Set `NEXT_PUBLIC_SITE_URL` to your deployed origin to make links usable by customers outside your local computer. Customers can preview their prepared message before opening WhatsApp.

## Run the backend in Docker with the frontend dev server

```bash
docker compose -f backend/compose.yaml up -d --build postgres redis api worker
docker compose -f backend/compose.yaml exec api uv run alembic upgrade head
COMMERCE_API_URL=http://127.0.0.1:8000 npm run dev:api -- -p 3001
```

Open `http://localhost:3001`. Local Docker allows storefront origins on ports 3000 and 3001. Tailwind scans only `src/` to keep backend and build-file changes from triggering frontend reloads.

## Check the implementation

```bash
npm run lint
npm run build
cd backend
uv run ruff check src tests
uv run mypy src
uv run pytest -q tests/unit tests/contract tests/integration
```

Set `TEST_DATABASE_URL` and `TEST_REDIS_URL` for database and Redis integration coverage. The destructive migration and bootstrap tests require their own disposable databases via `MIGRATION_DATABASE_URL` and `BOOTSTRAP_DATABASE_URL`.

See [INTEGRATION_REVIEW.md](INTEGRATION_REVIEW.md) for implemented journeys and remaining specification work.
