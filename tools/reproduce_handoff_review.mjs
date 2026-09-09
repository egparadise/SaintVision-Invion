import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const require = createRequire(import.meta.url);
const [folder, typescript] = process.argv.slice(2);
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
function luminance(hex) {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return channels.reduce((a, v, i) => a + v * [.2126, .7152, .0722][i], 0);
}
const background = luminance('#0d1117'), border = luminance('#30363d');
const result = {
  scope: 'Exact modules in memory; no browser audit, traffic, TLS session, training or deployment.',
  sloWithoutMeasurement: manager.getSloRecords().map(x => ({ name: x.name, status: x.status, value: x.actualValue })),
  auditsWithoutBrowser: manager.getAccessibilityAudits().map(x => ({ rule: x.ruleId, status: x.status })),
  rollbackWithoutDeployment: manager.rollbackToVersion('v1.0.0-rc.1').activeCandidate.rollbackVerified,
  futureEpochAccepted: isTokenValidAndCurrent({ epoch: 99, sequence: 1 }, { epoch: 1, sequence: 100 }),
  futureSequenceAccepted: isTokenValidAndCurrent({ epoch: 1, sequence: 999 }, { epoch: 1, sequence: 100 }),
  declaredBorderContrast: manager.getAccessibilityAudits()[1].contrastRatio,
  calculatedBorderContrast: (Math.max(background, border) + .05) / (Math.min(background, border) + .05),
  nodesWithoutTraffic: deployment.getNodeVerifications().map(x => ({ nodeId: x.nodeId, status: x.smokeStatus, latencyMs: x.latencyMs })),
  trainingWithoutAction: deployment.getTrainingSteps().map(x => x.status),
  signoffWithoutAuthentication: deployment.signOffRelease('arbitrary-actor').success,
  digestHas64Hex: /^sha256:[0-9a-f]{64}$/.test(deployment.getReleaseManifest().imageDigest),
  generatedConfigHasIndexNoCache: /location\s+=\s+\/index\.html/.test(deployment.generateNginxConfig()),
};
fs.writeFileSync(path.join(folder, 'frontend.json'), JSON.stringify(result, null, 2));
