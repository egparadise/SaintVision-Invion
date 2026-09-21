import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  projectWorkspacesFixture,
  workspaceExecutionReadinessFixture,
} from './fixtures/workspace-catalog';

function loadSchema(name: string) {
  return JSON.parse(readFileSync(
    new URL(`../../../contracts/${name}.schema.json`, import.meta.url),
    'utf8',
  ));
}

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
const validateWorkspaces = ajv.compile(loadSchema('project-workspaces-response'));
const validateReadiness = ajv.compile(loadSchema('workspace-execution-readiness-response'));

describe('workspace picker and execution readiness shared wire fixtures', () => {
  it('validates the workspace picker fixture against the backend schema', () => {
    expect(validateWorkspaces(projectWorkspacesFixture), JSON.stringify(validateWorkspaces.errors)).toBe(true);
  });

  it('rejects workspace fixture drift that omits allowed lifecycle actions', () => {
    const { allowedNext: _allowedNext, ...workspace } = projectWorkspacesFixture.workspaces[0];
    const changed = { ...projectWorkspacesFixture, workspaces: [workspace] };
    expect(validateWorkspaces(changed), JSON.stringify(validateWorkspaces.errors)).toBe(false);
  });

  it('validates the readiness checklist fixture against the backend schema', () => {
    expect(validateReadiness(workspaceExecutionReadinessFixture), JSON.stringify(validateReadiness.errors)).toBe(true);
  });

  it('rejects readiness drift that changes the precondition scope', () => {
    const changed = { ...workspaceExecutionReadinessFixture, executable: true };
    expect(validateReadiness(changed), JSON.stringify(validateReadiness.errors)).toBe(false);
  });
});
