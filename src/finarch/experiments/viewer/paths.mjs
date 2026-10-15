import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const projectDirectory = fileURLToPath(new URL('../../../../', import.meta.url));
export const assetDirectory = path.join(projectDirectory, 'viewer/experiments');
