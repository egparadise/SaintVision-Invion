import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, expect, it, vi } from 'vitest';
import { apiClient } from '../src/shared/api/client';
import { fabricObservation as fabric } from '../src/shared/api/fabricObservation';
import { InvFileExplorer } from '../src/features/desktop/InvFileExplorer';
import { ModelStudioView } from '../src/features/desktop/ModelStudioView';
vi.mock('../src/shared/api/client', () => ({apiClient: vi.fn()}));
const api = vi.mocked(apiClient);
beforeEach(() => { api.mockReset(); });
const location = {locationId: 'loc1', uri: 'inv://my-folder/a b#x', byteSize: 0, checksumSha256: null};
const observation = {locationId: 'loc1', observedAt: '2026-09-15T00:00:00Z', recordedStates: {ready: 2, transferring: 0, stale: 1, corrupt: 0, evicted: 3}, totalRecords: 6, currentAvailability: 'unknown', requiresExecutionRevalidation: true};
it('encodes URI and cursor, uses GET without caching, and propagates cancellation', async () => {
  const signal = new AbortController().signal;
  api.mockResolvedValueOnce({items: [], nextCursor: null}).mockResolvedValueOnce({location}).mockResolvedValueOnce({observation});
  await fabric.locations('a+b/=', signal); await fabric.resolve(location.uri, signal); await fabric.replicas(location, signal);
  expect(api.mock.calls[0][0]).toBe('/v1/storage/locations?limit=50&cursor=a%2Bb%2F%3D');
  expect(new URL(api.mock.calls[1][0], 'https://test').searchParams.get('uri')).toBe(location.uri);
  for (const [, options] of api.mock.calls) expect(options).toEqual({method: 'GET', cache: 'no-store', signal});
});
it('rejects a resolved URI from a different request', async () => {
  api.mockResolvedValue({location}); await expect(fabric.resolve('inv://other')).rejects.toThrow();
});
it.each([{locationId: 'other'}, {currentAvailability: 'ready'}, {requiresExecutionRevalidation: false}, {totalRecords: 3}, {recordedStates: {...observation.recordedStates, ready: -1}}, {recordedStates: {...observation.recordedStates, ready: 0.5}}])('rejects inconsistent replica observation %o', async patch => {
  api.mockResolvedValue({observation: {...observation, ...patch}}); await expect(fabric.replicas(location)).rejects.toThrow();
});
const model = {projectId: 'project', modelId: 'model', version: 'v1', committed: true, currentAvailability: 'unknown', requiresExecutionRevalidation: true};
it.each([{projectId: 'other'}, {modelId: 'other'}, {version: 'latest'}, {committed: false}, {currentAvailability: 'ready'}, {requiresExecutionRevalidation: false}])('rejects wrong model authority/scope %o', async patch => {
  api.mockResolvedValue({...model, ...patch}); await expect(fabric.model('project', 'model', 'v1')).rejects.toThrow();
});
it('preserves the model observation without promoting it to execution authority', async () => {
  api.mockResolvedValue(model); expect(await fabric.model('project', 'model', 'v1')).toEqual(model);
  expect(api).toHaveBeenCalledWith('/v1/projects/project/models/model/versions/v1/commitment', {method: 'GET', cache: 'no-store', signal: undefined});
});
it.each([401, 403, 404, 409])('does not retry or fall back after %i', async status => {
  api.mockRejectedValue({status}); await expect(fabric.model('project', 'model', 'v1')).rejects.toEqual({status}); expect(api).toHaveBeenCalledTimes(1);
});
it('starts with empty read-only views and no sample models or success controls', () => {
  const files = renderToStaticMarkup(<InvFileExplorer />);
  const models = renderToStaticMarkup(<ModelStudioView projectId="project" />);
  expect(files).toContain('등록된 파일이 없습니다'); expect(models).toContain('정확한 모델 ID');
  expect(files + models).not.toMatch(/llama|qwen|복구 완료|배포 완료|SAMPLE_/i);
  expect(api).not.toHaveBeenCalled();
});
