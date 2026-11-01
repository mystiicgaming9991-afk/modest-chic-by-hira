import { defineCliConfig } from 'sanity/cli';
import catalogue from '../catalogue.config.json';

export default defineCliConfig({
  api: { projectId: catalogue.projectId, dataset: catalogue.dataset },
  studioHost: `modest-chic-${catalogue.projectId}`,
  deployment: { appId: 'ev8ciliojeeulkedy64bn6xa', autoUpdates: false },
});
