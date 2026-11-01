import { defineConfig } from 'sanity';
import { structureTool } from 'sanity/structure';
import catalogue from '../catalogue.config.json';
import { schemaTypes } from './schema';

export default defineConfig({
  name: 'modest-chic',
  title: 'Modest Chic Catalogue',
  projectId: catalogue.projectId,
  dataset: catalogue.dataset,
  plugins: [structureTool({
    structure: (S) => S.list().title('Catalogue').items([
      S.documentTypeListItem('product').title('Products'),
      S.divider(),
      S.documentTypeListItem('category').title('Categories'),
      S.documentTypeListItem('collection').title('Collections'),
    ]),
  })],
  schema: { types: schemaTypes },
});
