import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { projectListFixture } from './fixtures/workspace-catalog';

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
const root = new URL('../../../contracts/', import.meta.url);
const schema = (name: string) => JSON.parse(readFileSync(new URL(`${name}.schema.json`, root), 'utf8'));
const validateBusinessList = ajv.compile(schema('project-list-response'));

describe('project picker response contracts shared with provider fixtures', () => {
  it('accepts the canonical projects envelope against backend schema', () => {
    expect(validateBusinessList(projectListFixture), JSON.stringify(validateBusinessList.errors)).toBe(true);
  });

  it('rejects a canonical project row missing its display label', () => {
    const changed = structuredClone(projectListFixture);
    delete (changed.projects[0] as Partial<typeof changed.projects[0]>).displayName;
    expect(validateBusinessList(changed)).toBe(false);
  });

});
