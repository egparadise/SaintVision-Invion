import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const require = createRequire(import.meta.url);
const rawArgs = process.argv.slice(2);
const positional = [];
let outputPath;
let selfTest = false;
for (let i = 0; i < rawArgs.length; i++) {
  const arg = rawArgs[i];
  if (arg === '--self-test') {
    selfTest = true;
  } else if (arg === '--output' && rawArgs[i + 1]) {
    outputPath = rawArgs[++i];
  } else if (arg.startsWith('--output=')) {
    outputPath = arg.slice('--output='.length);
  } else if (arg.startsWith('--')) {
    console.error('Usage error: unknown option. Usage: node tools/reproduce_handoff_review.mjs <folder> <typescript-module> [--output <path>] [--self-test]');
    process.exit(2);
  } else {
    positional.push(arg);
  }
}
if (positional.length !== 2) {
  console.error('Usage error: expected <folder> and <typescript-module>. Usage: node tools/reproduce_handoff_review.mjs <folder> <typescript-module> [--output <path>] [--self-test]');
  process.exit(2);
}
const [folder, typescript] = positional;
outputPath ||= path.join(folder, '.work', 'reproduce-handoff', 'frontend.json');
const ts = require(typescript);
async function load(relative) {
  const source = fs.readFileSync(path.join(folder, relative), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
  return import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
}
const { ReleaseManager } = await load('apps/web/src/features/release/releaseEngine.ts');
const { isTokenValidAndCurrent } = await load('apps/web/src/features/recovery/recoveryEngine.ts');
const { DeploymentManager } = await load('apps/web/src/features/deployment/deploymentEngine.ts');
const manager = new ReleaseManager(), deployment = new DeploymentManager();
const failures = [];
const unverified = [];

function expectValue(name, actual, expected) {
  if (actual === expected) {
    console.log(`PASS ${name}: ${String(actual)}`);
    return true;
  }
  failures.push({ name, actual, expected });
  console.error(`FAIL ${name}: expected ${String(expected)}, got ${String(actual)}`);
  return false;
}

function markUnverified(name, reason, value) {
  unverified.push({ name, reason, value });
  console.log(`UNVERIFIED ${name}: ${reason}`);
}
function luminance(hex) {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return channels.reduce((a, v, i) => a + v * [.2126, .7152, .0722][i], 0);
}
const background = luminance('#0d1117'), border = luminance('#30363d');
const sloWithoutMeasurement = manager.getSloRecords().map(x => ({ name: x.name, status: x.status, value: x.actualValue }));
const auditsWithoutBrowser = manager.getAccessibilityAudits().map(x => ({ rule: x.ruleId, status: x.status }));
const rollbackWithoutDeployment = manager.rollbackToVersion('v1.0.0-rc.1').activeCandidate?.rollbackVerified;
const futureEpochAccepted = isTokenValidAndCurrent({ epoch: 99, sequence: 1 }, { epoch: 1, sequence: 100 });
const futureSequenceAccepted = isTokenValidAndCurrent({ epoch: 1, sequence: 999 }, { epoch: 1, sequence: 100 });
const declaredBorderContrast = manager.getAccessibilityAudits()[1].contrastRatio;
const calculatedBorderContrast = (Math.max(background, border) + .05) / (Math.min(background, border) + .05);
const nodesWithoutTraffic = deployment.getNodeVerifications().map(x => ({ nodeId: x.nodeId, status: x.smokeStatus, latencyMs: x.latencyMs }));
const trainingWithoutAction = deployment.getTrainingSteps().map(x => x.status);
const signoffWithoutAuthentication = deployment.signOffRelease('arbitrary-actor').success;
const digestHas64Hex = /^sha256:[0-9a-f]{64}$/.test(deployment.getReleaseManifest().imageDigest);
const generatedConfigHasIndexNoCache = /try_files\s+\$uri\s+\$uri\/\s+\/index\.html/.test(deployment.generateNginxConfig());

// These are deterministic helper safety invariants and may fail the command.
expectValue('future epoch token is rejected', futureEpochAccepted, false);
expectValue('future sequence token is rejected', futureSequenceAccepted, false);
expectValue('unauthenticated sign-off is rejected', signoffWithoutAuthentication, false);
expectValue('release manifest has a sha256 digest', digestHas64Hex, true);
expectValue('generated nginx config has SPA index fallback', generatedConfigHasIndexNoCache, true);
expectValue('in-memory rollback selects the requested candidate', rollbackWithoutDeployment, true);

// These values are helper snapshots, not browser/traffic/deployment evidence.
markUnverified('SLO records', 'no measured telemetry/evidence was supplied', sloWithoutMeasurement);
markUnverified('accessibility audits', 'no browser or assistive-technology session was run', auditsWithoutBrowser);
markUnverified('rollback operational acceptance', 'helper simulation only; no deployment was performed', rollbackWithoutDeployment);
markUnverified('node verification traffic', 'no node or network traffic was observed', nodesWithoutTraffic);
markUnverified('training completion', 'no training action or physical resource was executed', trainingWithoutAction);
markUnverified('declared vs calculated contrast', 'local color calculation is not a browser rendering measurement', { declaredBorderContrast, calculatedBorderContrast });

if (selfTest) {
  // Deliberately exercise the failure path. This command must exit nonzero.
  expectValue('SELF-TEST intentional mismatch', true, false);
}

const result = {
  scope: 'Exact TypeScript modules in memory; helper calculations only. No browser audit, traffic, TLS session, training, deployment, or physical-node acceptance.',
  sloWithoutMeasurement,
  auditsWithoutBrowser,
  rollbackWithoutDeployment,
  futureEpochAccepted,
  futureSequenceAccepted,
  declaredBorderContrast,
  calculatedBorderContrast,
  nodesWithoutTraffic,
  trainingWithoutAction,
  signoffWithoutAuthentication,
  digestHas64Hex,
  generatedConfigHasIndexNoCache,
  failures,
  unverified,
  selfTest,
};
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
if (failures.length > 0) process.exitCode = 1;
