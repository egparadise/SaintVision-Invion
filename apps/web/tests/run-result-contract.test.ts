import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { runResultViewFixture, runArtifactListFixture, artifactContentResponseFixture } from './fixtures/run-result';

const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);

const validateResultView = ajv.compile({ $ref: `${schema.$id}#/$defs/RunResultView` });
const validateArtifactList = ajv.compile({ $ref: `${schema.$id}#/$defs/RunArtifactList` });
const validateArtifactContent = ajv.compile({ $ref: `${schema.$id}#/$defs/ArtifactContentResponse` });

describe('kernel run result, artifact list & content shared wire fixtures', () => {
  it('validates runResultViewFixture against core.schema.json #/$defs/RunResultView', () => {
    expect(validateResultView(runResultViewFixture), JSON.stringify(validateResultView.errors)).toBe(true);
  });

  it('rejects runResultViewFixture when required field "output" is removed', () => {
    const { output: _output, ...broken } = runResultViewFixture;
    expect(validateResultView(broken), JSON.stringify(validateResultView.errors)).toBe(false);
  });

  it('validates runArtifactListFixture against core.schema.json #/$defs/RunArtifactList', () => {
    expect(validateArtifactList(runArtifactListFixture), JSON.stringify(validateArtifactList.errors)).toBe(true);
  });

  it('rejects runArtifactListFixture when required field "artifacts" is removed', () => {
    const { artifacts: _artifacts, ...broken } = runArtifactListFixture;
    expect(validateArtifactList(broken), JSON.stringify(validateArtifactList.errors)).toBe(false);
  });

  it('validates the raw artifact HTTP metadata fixture against the canonical schema', () => {
    expect(validateArtifactContent(artifactContentResponseFixture), JSON.stringify(validateArtifactContent.errors)).toBe(true);
  });

  it('rejects artifact metadata when its body digest is absent or its media type drifts', () => {
    const { checksumSha256: _checksumSha256, ...artifactWithoutDigest } = artifactContentResponseFixture.artifact;
    const missingDigest = { ...artifactContentResponseFixture, artifact: artifactWithoutDigest };
    expect(validateArtifactContent(missingDigest), JSON.stringify(validateArtifactContent.errors)).toBe(false);
    expect(validateArtifactContent({ ...artifactContentResponseFixture, contentType: 'application/json' }),
      JSON.stringify(validateArtifactContent.errors)).toBe(false);
  });
});
