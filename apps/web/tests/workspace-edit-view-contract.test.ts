import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchWorkspaceEditView, mapWorkspaceFilesToInvItems } from '../src/shared/api/workspaceEditObservation';
import { apiClient } from '../src/shared/api/client';

vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validateWorkspaceEdit = ajv.compile({ $ref: `${schema.$id}#/$defs/WorkspaceEditView` });
const readFixture = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../../contracts/fixtures/${name}`, import.meta.url), 'utf8'));

describe('WorkspaceEditView contract fixture and workspaceEditObservation consumer', () => {
  beforeEach(() => api.mockReset());

  it('validates the shared workspace-edit-view fixture against canonical backend schema', () => {
    const fixture = readFixture('workspace-edit-view-response.json');
    expect(validateWorkspaceEdit(fixture), JSON.stringify(validateWorkspaceEdit.errors)).toBe(true);
  });

  it('rejects workspace-edit-view fixture with non-hex sha256 digest', () => {
    const changed = readFixture('workspace-edit-view-response.json');
    changed.sha256 = 'not-a-valid-hex-sha256-hash';
    expect(validateWorkspaceEdit(changed)).toBe(false);
  });

  it('rejects workspace-edit-view fixture with missing required checkoutId', () => {
    const changed = readFixture('workspace-edit-view-response.json');
    delete changed.checkoutId;
    expect(validateWorkspaceEdit(changed)).toBe(false);
  });

  it('rejects workspace-edit-view fixture when file missing required sha256', () => {
    const changed = readFixture('workspace-edit-view-response.json');
    delete changed.snapshot.files[0].sha256;
    expect(validateWorkspaceEdit(changed)).toBe(false);
  });

  it('fetchWorkspaceEditView fetches and validates canonical response', async () => {
    const fixture = readFixture('workspace-edit-view-response.json');
    api.mockResolvedValue(fixture);

    const result = await fetchWorkspaceEditView('prj_01', 'run_01', fixture.checkoutId);

    expect(result).toEqual(fixture);
    expect(result.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(api).toHaveBeenCalledWith(
      `/v1/projects/prj_01/runs/run_01/checkouts/${encodeURIComponent(fixture.checkoutId)}/files`,
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('fetchWorkspaceEditView throws when response sha256 is invalid', async () => {
    const fixture = readFixture('workspace-edit-view-response.json');
    api.mockResolvedValue({
      ...fixture,
      sha256: 'invalid-hash',
    });

    await expect(
      fetchWorkspaceEditView('prj_01', 'run_01', fixture.checkoutId)
    ).rejects.toThrow('WorkspaceEditView 응답 계약 불일치');
  });

  it('mapWorkspaceFilesToInvItems converts snapshot files to InvFileItem with kernel-checkout source', () => {
    const fixture = readFixture('workspace-edit-view-response.json');
    const items = mapWorkspaceFilesToInvItems(fixture);

    expect(items).toHaveLength(1);
    const item = items[0];
    expect(item.source).toBe('kernel-checkout');
    expect(item.relativePath).toBe('src/main.py');
    expect(item.contentHash).toBe('ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff');
    expect(item.content).toBe("print('hello')\n");
    expect(item.namespace).toBe('workspaces');
    expect(item.replicas).toEqual([]);
    expect(item.uri).toBe('inv://workspaces/wsp_0123456789ABCDEFGHJKMNPQRS/src/main.py');
    expect(item.decodeError).toBeUndefined();
  });

  it('fetchWorkspaceEditView throws when snapshot workspaceId is missing or empty', async () => {
    const fixture = readFixture('workspace-edit-view-response.json');
    delete fixture.snapshot.workspaceId;
    api.mockResolvedValue(fixture);

    await expect(
      fetchWorkspaceEditView('prj_01', 'run_01', fixture.checkoutId)
    ).rejects.toThrow('WorkspaceEditView 응답 계약 불일치');
  });

  it('mapWorkspaceFilesToInvItems strictly throws when workspaceId is missing (no silent default-workspace fallback)', () => {
    const fixture = readFixture('workspace-edit-view-response.json');
    const corrupted = {
      ...fixture,
      snapshot: {
        ...fixture.snapshot,
        workspaceId: '',
      },
    };

    expect(() => mapWorkspaceFilesToInvItems(corrupted as any)).toThrow(
      'WorkspaceSnapshot에 유효한 workspaceId가 누락되었습니다'
    );
  });

  it('mapWorkspaceFilesToInvItems handles base64 decode failure honestly (sets content=undefined and records decodeError)', () => {
    const fixture = readFixture('workspace-edit-view-response.json');
    const corrupted = {
      ...fixture,
      snapshot: {
        ...fixture.snapshot,
        files: [
          {
            ...fixture.snapshot.files[0],
            dataBase64: '!!!broken-base64-not-decodable!!!',
          },
        ],
      },
    };

    const items = mapWorkspaceFilesToInvItems(corrupted as any);
    expect(items).toHaveLength(1);
    const item = items[0];
    expect(item.content).toBeUndefined();
    expect(item.decodeError).toBeDefined();
    expect(item.decodeError).toContain('Base64 디코딩 실패');
  });
});
