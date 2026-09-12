import { describe, it, expect } from 'vitest';
import { DeploymentManager } from '../src/features/deployment/deploymentEngine';

describe('S12-FE: Intranet HTTPS Web Deployment, 5-Node Journey & Training Walkthrough (AC-12)', () => {
  describe('TLS 1.3 & Nginx Reverse Proxy Architecture', () => {
    it('verifies strict TLS 1.3 certificate parameters, HSTS, and SAN list', () => {
      const dm = new DeploymentManager();
      const tls = dm.getTlsDetails();

      expect(tls.domain).toBe('saintvision.internal');
      expect(tls.tlsVersion).toContain('TLSv1.3');
      expect(tls.cipherSuite).toContain('TLS_AES_256_GCM_SHA384');
      expect(tls.hstsEnabled).toBe(true);
      expect(tls.sanList).toContain('saintvision.internal');
      expect(tls.sanList).toContain('*.node.saintvision.internal');
      expect(tls.sanList.length).toBeGreaterThanOrEqual(5);
    });

    it('verifies Nginx single-origin reverse proxy routing and buffering rules', () => {
      const dm = new DeploymentManager();
      const rules = dm.getNginxRules();

      // Static SPA rule
      const staticRule = rules.find((r) => r.location === '/');
      expect(staticRule).toBeDefined();
      expect(staticRule?.cacheControl).toContain('immutable');

      // SSE Event Streaming rule (Buffering must be disabled)
      const sseRule = rules.find((r) => r.location === '/v1/events');
      expect(sseRule).toBeDefined();
      expect(sseRule?.protocol).toBe('SSE');
      expect(sseRule?.bufferingOff).toBe(true);

      // WebSocket Terminal rule (Upgrade header required)
      const wsRule = rules.find((r) => r.location === '/v1/terminal/ws');
      expect(wsRule).toBeDefined();
      expect(wsRule?.protocol).toBe('WebSocket');
      expect(wsRule?.upgradeHeader).toBe(true);

      // Canonical Workspace Terminal rule (ADR-038)
      const canonicalWsRule = rules.find((r) => r.location.includes('/terminals/'));
      expect(canonicalWsRule).toBeDefined();
      expect(canonicalWsRule?.protocol).toBe('WebSocket');
      expect(canonicalWsRule?.upgradeHeader).toBe(true);
    });

    it('generates production-grade nginx.conf containing SSL and reverse proxy directives', () => {
      const dm = new DeploymentManager();
      const conf = dm.generateNginxConfig();

      expect(conf).toContain('listen 8443 ssl http2;');
      expect(conf).toContain('ssl_protocols TLSv1.3;');
      expect(conf).toContain('Strict-Transport-Security');
      expect(conf).toContain('proxy_buffering off;');
      expect(conf).toContain('proxy_set_header Upgrade $http_upgrade;');
      expect(conf).toContain('try_files $uri $uri/ /index.html;');
      expect(conf).toContain('location ~ ^/v1/workspaces/[^/]+/terminals/');
    });
  });

  describe('5-Node Full E2E Journey & Smoke Verification (AC-12)', () => {
    it('verifies all 5 nodes (3 Windows, 2 Linux) successfully pass smoke checks', () => {
      const dm = new DeploymentManager();
      const nodes = dm.getNodeVerifications();

      expect(nodes).toHaveLength(5);

      const windowsNodes = nodes.filter((n) => n.os === 'windows');
      const linuxNodes = nodes.filter((n) => n.os === 'linux');
      expect(windowsNodes).toHaveLength(3);
      expect(linuxNodes).toHaveLength(2);

      // All nodes must pass smoke tests with low intranet latency
      nodes.forEach((node) => {
        expect(node.smokeStatus).toBe('passed');
        expect(node.latencyMs).toBeLessThanOrEqual(30);
        expect(node.roles.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Release Manifest & Operator Sign-off Workflow (AC-12)', () => {
    it('validates Release R4 manifest metadata and immutable image digest', () => {
      const dm = new DeploymentManager();
      const manifest = dm.getReleaseManifest();

      expect(manifest.releaseId).toBe('REL-2026-R4-GA');
      expect(manifest.version).toBe('v1.0.0-final-GA');
      expect(manifest.imageDigest).toMatch(/^sha256:[0-9a-f]{64}$/);
      expect(manifest.totalNodes).toBe(5);
      expect(manifest.smokePassedRatio).toBe(100.0);
      expect(manifest.knownLimitations.length).toBeGreaterThanOrEqual(3);
    });

    it('requires valid operator ID and signs off final GA release', () => {
      const dm = new DeploymentManager();

      // Empty operator ID rejected
      const attempt1 = dm.signOffRelease('');
      expect(attempt1.success).toBe(false);
      expect(attempt1.error).toContain('Operator ID is required');

      // Unauthorized arbitrary actor rejected
      const attemptUnauthorized = dm.signOffRelease('arbitrary-actor');
      expect(attemptUnauthorized.success).toBe(false);
      expect(attemptUnauthorized.error).toContain('Unauthorized operator');

      // Valid operator sign-off succeeded
      const attempt2 = dm.signOffRelease('usr_operator_lead');
      expect(attempt2.success).toBe(true);
      expect(attempt2.manifest.operatorSignOff).toBe(true);
    });
  });

  describe('Operator Training & Education Walkthrough (AC-12)', () => {
    it('contains all 4 essential operator training modules and records completion', () => {
      const dm = new DeploymentManager();
      const steps = dm.getTrainingSteps();

      expect(steps).toHaveLength(4);
      expect(steps[0].title).toContain('L0~L3 거버넌스');
      expect(steps[1].title).toContain('자원 배치');
      expect(steps[2].title).toContain('Kill Switch');
      expect(steps[3].title).toContain('무중단 롤백');

      const result = dm.completeTrainingStep(2);
      expect(result.success).toBe(true);
      const step2 = result.steps.find((s) => s.stepNumber === 2);
      expect(step2?.status).toBe('completed');
    });
  });

  describe('Preflight Pipeline vs Physical Hardware Acceptance (AC-12 Zero-Mock)', () => {
    it('returns verified preflight status with 154 checks and pending physical hardware acceptance', () => {
      const dm = new DeploymentManager();
      const preflight = dm.getPreflightStatus();

      expect(preflight.isPreflightPassed).toBe(true);
      expect(preflight.tlsVerified).toBe(true);
      expect(preflight.nginxRoutingVerified).toBe(true);
      expect(preflight.smokeChecksCount).toBe(154);
      expect(preflight.smokePassedRatio).toBe(100.0);
      expect(preflight.physicalHardwareAcceptance).toBe('pending');

      // Once signed off, physical hardware acceptance transitions to accepted
      dm.signOffRelease('usr_operator_lead');
      const updated = dm.getPreflightStatus();
      expect(updated.physicalHardwareAcceptance).toBe('accepted');
    });

    it('reconciles live cluster node states including draining and observation-only flags', () => {
      const dm = new DeploymentManager();
      const liveNodes = [
        {
          id: 'nod_01JABCDEF01',
          hostname: 'Node-01-WinMain',
          status: 'online' as const,
          os: 'windows' as const,
          cpuCores: 16,
          cpuUsagePercent: 25,
          memoryTotalBytes: 64 * 1024 * 1024 * 1024,
          memoryUsedBytes: 16 * 1024 * 1024 * 1024,
          gpuCount: 1,
          storageTotalBytes: 1000,
          storageUsedBytes: 100,
          heartbeatAt: new Date().toISOString(),
          schedulable: true,
          isDraining: false,
        },
        {
          id: 'nod_01JABCDEF02',
          hostname: 'Node-02-WinWork',
          status: 'draining' as const,
          os: 'windows' as const,
          cpuCores: 8,
          cpuUsagePercent: 50,
          memoryTotalBytes: 32 * 1024 * 1024 * 1024,
          memoryUsedBytes: 16 * 1024 * 1024 * 1024,
          gpuCount: 0,
          storageTotalBytes: 1000,
          storageUsedBytes: 100,
          heartbeatAt: new Date().toISOString(),
          schedulable: false,
          isDraining: true,
        },
      ];

      const reconciled = dm.reconcileLiveClusterNodes(liveNodes);
      expect(reconciled).toHaveLength(5);

      const node01 = reconciled.find((n) => n.nodeId === 'nod_01JABCDEF01');
      expect(node01?.liveStatus).toBe('online');
      expect(node01?.liveSchedulable).toBe(true);
      expect(node01?.liveIsDraining).toBe(false);

      const node02 = reconciled.find((n) => n.nodeId === 'nod_01JABCDEF02');
      expect(node02?.liveStatus).toBe('draining');
      expect(node02?.liveSchedulable).toBe(false);
      expect(node02?.liveIsDraining).toBe(true);

      // Architecture node without live telemetry retains base smoke status
      const node03 = reconciled.find((n) => n.nodeId === 'nod_01JABCDEF03');
      expect(node03?.smokeStatus).toBe('passed');
      expect(node03?.liveStatus).toBeUndefined();
    });
  });
});

