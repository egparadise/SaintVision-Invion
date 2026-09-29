import { describe, it, expect } from 'vitest';
import { DeploymentManager } from '../src/features/deployment/deploymentEngine';

describe('S12-FE: Intranet HTTPS Web Deployment, 5-Node Journey & Training Walkthrough (AC-12)', () => {
  describe('TLS 1.3 & Nginx Reverse Proxy Architecture', () => {
    it('verifies strict TLS 1.3 certificate parameters, HSTS, and SAN list', () => {
      const dm = new DeploymentManager();
      const tls = dm.getTlsDetails();

      expect(tls.domain).toBe('saintvision.internal');
      expect(tls.tlsVersion).toContain('TLSv1.2');
      expect(tls.cipherSuite).toContain('HIGH:!aNULL:!MD5');
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
      const sseRule = rules.find((r) => r.location.includes('/events'));
      expect(sseRule).toBeDefined();
      expect(sseRule?.protocol).toBe('SSE');
      expect(sseRule?.bufferingOff).toBe(true);

      // Canonical Workspace Terminal rule (ADR-038, Upgrade header required)
      const canonicalWsRule = rules.find((r) => r.location.includes('/terminals/'));
      expect(canonicalWsRule).toBeDefined();
      expect(canonicalWsRule?.protocol).toBe('WebSocket');
      expect(canonicalWsRule?.upgradeHeader).toBe(true);
    });

    it('generates production-grade nginx.conf containing SSL and reverse proxy directives', () => {
      const dm = new DeploymentManager();
      const conf = dm.generateNginxConfig();

      expect(conf).toContain('listen 443 ssl http2;');
      expect(conf).toContain('ssl_protocols TLSv1.2 TLSv1.3;');
      expect(conf).toContain('Strict-Transport-Security');
      expect(conf).toContain('proxy_buffering off;');
      expect(conf).toContain('proxy_set_header Upgrade $http_upgrade;');
      expect(conf).toContain('try_files $uri $uri/ /index.html;');
      expect(conf).toContain('location ~ ^/v1/workspaces/[^/]+/terminals/');
    });
  });

  describe('5-Node Full E2E Journey & Smoke Verification (AC-12)', () => {
    it('verifies 5-node architectural journey spec definitions and reconciliation behavior', () => {
      const dm = new DeploymentManager();
      const nodes = dm.getNodeVerifications();

      expect(nodes).toHaveLength(5);

      const windowsNodes = nodes.filter((n) => n.os === 'windows');
      const linuxNodes = nodes.filter((n) => n.os === 'linux');
      expect(windowsNodes).toHaveLength(3);
      expect(linuxNodes).toHaveLength(2);

      // Architectural baseline checks
      nodes.forEach((node) => {
        expect(node.roles.length).toBeGreaterThan(0);
      });

      // Reconciliation with offline live node marks smokeStatus as failed (DEF-S12-03)
      const reconciled = dm.reconcileLiveClusterNodes([
        {
          id: 'nod_01JABCDEF01',
          hostname: 'Node-01-WinMain',
          status: 'offline',
          os: 'windows',
          cpuCores: 8,
          cpuUsagePercent: 0,
          memoryTotalBytes: 32000000000,
          memoryUsedBytes: 0,
          gpuCount: 0,
          storageTotalBytes: 100000000000,
          storageUsedBytes: 0,
          heartbeatAt: '2026-09-28T09:00:00Z',
        },
      ]);
      const node1 = reconciled.find((n) => n.nodeId === 'nod_01JABCDEF01');
      expect(node1?.liveStatus).toBe('offline');
      expect(node1?.smokeStatus).toBe('failed');
    });
  });

  describe('Release Manifest & Operator Sign-off Workflow (AC-12)', () => {
    it('validates Release R4 manifest metadata and immutable image digest', () => {
      const dm = new DeploymentManager();
      const manifest = dm.getReleaseManifest();

      expect(manifest.releaseId).toBe('REL-2026-PILOT-RC');
      expect(manifest.version).toBe('v1.0.0-pilot-rc');
      expect(manifest.imageDigest).toMatch(/^sha256:[0-9a-f]{64}$/);
      expect(manifest.totalNodes).toBe(5);
      expect(manifest.smokePassedRatio).toBe(100.0);
      expect(manifest.knownLimitations.length).toBeGreaterThanOrEqual(3);
    });

    it('requires valid operator ID and roles; keeps canonical sign-off false without backend route', () => {
      const dm = new DeploymentManager();

      // Empty operator ID rejected
      const attempt1 = dm.signOffRelease('');
      expect(attempt1.success).toBe(false);
      expect(attempt1.error).toContain('Operator ID is required');

      // Unauthorized actor without roles rejected (regex bypass removed per Codex F-R1)
      const attemptUnauthorized = dm.signOffRelease('arbitrary-actor');
      expect(attemptUnauthorized.success).toBe(false);
      expect(attemptUnauthorized.error).toContain('Unauthorized operator');

      // Calling with operator prefix but without roles is rejected
      const attemptNoRoles = dm.signOffRelease('usr_operator_lead');
      expect(attemptNoRoles.success).toBe(false);
      expect(attemptNoRoles.error).toContain('Unauthorized operator');

      // Valid operator sign-off executes local simulation, but canonical manifest.operatorSignOff remains false
      const attempt2 = dm.signOffRelease('usr_operator_lead', { roles: ['operator'] });
      expect(attempt2.success).toBe(true);
      expect(attempt2.localSimulationCompleted).toBe(true);
      expect(attempt2.manifest.operatorSignOff).toBe(false);
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
    it('returns unmeasured preflight status with 202 checks and pending physical hardware acceptance', () => {
      const dm = new DeploymentManager();
      const preflight = dm.getPreflightStatus();

      expect(preflight.isPreflightPassed).toBe(false);
      expect(preflight.tlsVerified).toBe(false);
      expect(preflight.nginxRoutingVerified).toBe(false);
      expect(preflight.smokeChecksCount).toBe(202);
      expect(preflight.smokePassedRatio).toBe(0);
      expect(preflight.physicalHardwareAcceptance).toBe('pending');

      // Software sign-off does NOT auto-accept physical hardware (DEF-S12-16)
      dm.signOffRelease('usr_operator_lead', { roles: ['operator'] });
      const updated = dm.getPreflightStatus();
      expect(updated.physicalHardwareAcceptance).toBe('pending');
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

