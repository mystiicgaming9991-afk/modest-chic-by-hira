import { getCliClient } from 'sanity/cli';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import catalogue from '../../src/content/catalog.json';
import config from '../../catalogue.config.json';

const client = getCliClient({ apiVersion: config.apiVersion });
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const images = new Map<string, string>();
let transaction = client.transaction();
for (const [type, rows] of [['category', catalogue.categories], ['collection', catalogue.collections]] as const) {
  for (const row of rows) {
    // Sanity IDs containing dots are private even in a public dataset.
    const id = `${type}-${row.slug}`;
    if (await client.getDocument(id)) continue;
    if (!images.has(row.image)) {
      const asset = await client.assets.upload('image', createReadStream(path.join(root, 'public', row.image)), { filename: path.basename(row.image) });
      images.set(row.image, asset._id);
    }
    transaction = transaction.createIfNotExists({
      _id: id, _type: type, title: row.title,
      slug: { _type: 'slug', current: row.slug }, description: row.description,
      image: { _type: 'image', asset: { _type: 'reference', _ref: images.get(row.image) } },
    });
  }
}
await transaction.commit();
console.log('Initial categories and collections are ready. Existing documents were not replaced; no products were added.');
