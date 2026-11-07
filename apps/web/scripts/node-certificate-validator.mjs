// Build-time only. Never import this module from browser source.
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import standaloneCode from 'ajv/dist/standalone/index.js';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const schemaPath = resolve(webRoot, '../../contracts/v1alpha1/core.schema.json');
const [mode, directory = resolve(webRoot, 'src/contracts'), ...extra] = process.argv.slice(2);
if (!['--write', '--check'].includes(mode) || extra.length) {
  throw new Error('Usage: node scripts/node-certificate-validator.mjs (--write|--check) [output-directory]');
}
const sha256 = value => createHash('sha256').update(value).digest('hex');
const schemaBytes = await readFile(schemaPath);
const schema = JSON.parse(schemaBytes);
// Same draft, options, full formats and canonical $ref as the former runtime validator.
const ajv = new Ajv2020({ strict: false, code: { source: true } });
addFormats(ajv);
ajv.addSchema(schema);
const ref = `${schema.$id}#/$defs/ProjectNodeCertificateObservationResponse`;
const validate = ajv.compile({ $ref: ref });
const code = '// Generated at build time from contracts/v1alpha1/core.schema.json. Do not edit.\n'
  + standaloneCode(ajv, validate) + '\n';
const lockBytes = await readFile(resolve(webRoot, 'package-lock.json'));
const lock = JSON.parse(lockBytes);
const manifest = JSON.stringify({
  schema: 'contracts/v1alpha1/core.schema.json', ref,
  schemaSHA256: sha256(schemaBytes),
  generatorSHA256: sha256(await readFile(fileURLToPath(import.meta.url))),
  lockSHA256: sha256(lockBytes),
  ajv: lock.packages['node_modules/ajv'].version,
  ajvFormats: lock.packages['node_modules/ajv-formats'].version,
  validatorSHA256: sha256(code),
}, null, 2) + '\n';

for (const [name, expected] of [
  ['node-certificate-validator.cjs', code],
  ['node-certificate-validator.manifest.json', manifest],
]) {
  const path = resolve(directory, name);
  if (mode === '--write') {
    await mkdir(directory, { recursive: true });
    await writeFile(path, expected);
  } else if (await readFile(path, 'utf8').catch(() => null) !== expected) {
    throw new Error(`Generated validator drift: ${name}; run npm run validators:generate`);
  }
}
console.log(`PASS: canonical Node certificate standalone validator ${mode}; schema=${sha256(schemaBytes)} validator=${sha256(code)}`);
