import { cp, mkdir, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { validateCatalog } from './validate-catalog.mjs';
import { cloudflareSecurityHeaders, secureStaticHtml } from './static-security.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const stage = path.join(root, '.static-site');
const catalog = await validateCatalog(root);
await rm(stage, { recursive: true, force: true });
await mkdir(stage, { recursive: true });
// Build an isolated storefront. The original API routes, admin and backend stay intact.
await cp(path.join(root, 'src'), path.join(stage, 'src'), {
  recursive: true,
  filter: (source) => {
    const relative = path.relative(path.join(root, 'src'), source).split(path.sep).join('/');
    return !/\.test\.[^.]+$/.test(relative) && !/^app\/(api|admin)(\/|$)/.test(relative)
      && !/^app\/\(storefront\)\/(account|checkout|order-confirmation)(\/|$)/.test(relative);
  },
});
await cp(path.join(root, 'static/app'), path.join(stage, 'src/app'), { recursive: true });
if (!catalog.products.length) await rm(path.join(stage, 'src/app/(storefront)/shop/[slug]'), { recursive: true, force: true });
if (!catalog.collections.length) await rm(path.join(stage, 'src/app/(storefront)/collections/[slug]'), { recursive: true, force: true });
await cp(path.join(root, 'public'), path.join(stage, 'public'), { recursive: true });
for (const filename of ['package.json', 'tsconfig.json']) await cp(path.join(root, filename), path.join(stage, filename));
await symlink(path.join(root, 'node_modules'), path.join(stage, 'node_modules'), 'dir');
const number = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER ?? '923144660921';
// Only explicitly public settings enter the static output. No backend credentials are copied.
await writeFile(path.join(stage, 'next.config.ts'), `import type { NextConfig } from 'next';
const config: NextConfig = {
 output: 'export', trailingSlash: true, images: { unoptimized: true },
 env: { NEXT_PUBLIC_STOREFRONT_MODE: 'static', NEXT_PUBLIC_WHATSAPP_NUMBER: ${JSON.stringify(number)}, NEXT_PUBLIC_SITE_URL: ${JSON.stringify(process.env.NEXT_PUBLIC_SITE_URL ?? '')}, NEXT_PUBLIC_GA_MEASUREMENT_ID: ${JSON.stringify(process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ?? '')} },
 turbopack: { root: ${JSON.stringify(root)}, rules: { '*.css': { loaders: ['@tailwindcss/turbopack'], as: '*.css' } } }
}; export default config;\n`);
const code = await new Promise((resolve, reject) => {
  const child = spawn(process.execPath, [path.join(root, 'node_modules/next/dist/bin/next'), 'build'], { cwd: stage, stdio: 'inherit', env: { ...process.env, NEXT_PUBLIC_STOREFRONT_MODE: 'static' } });
  child.on('error', reject); child.on('exit', resolve);
});
if (code !== 0) process.exit(code ?? 1);
await rm(path.join(root, 'out'), { recursive: true, force: true });
await cp(path.join(stage, 'out'), path.join(root, 'out'), { recursive: true });
const analyticsEnabled = /^G-[A-Z0-9]+$/.test(process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ?? '');
async function secureHtmlFiles(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) await secureHtmlFiles(filename);
    else if (entry.name.endsWith('.html')) {
      const html = await readFile(filename, 'utf8');
      await writeFile(filename, secureStaticHtml(html, { analyticsEnabled }));
    }
  }
}
await secureHtmlFiles(path.join(root, 'out'));
// Host-level headers/redirects replace Next server-only configuration.
await writeFile(path.join(root, 'out/_headers'), cloudflareSecurityHeaders());
await writeFile(path.join(root, 'out/_redirects'), '/checkout /cart/ 302\n/checkout/ /cart/ 302\n');
console.log('Static storefront ready in out/. No Python, database or Next.js server is needed.');
