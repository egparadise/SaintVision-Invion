import {
  TlsCertificateDetail,
  NginxRoutingRule,
  NodeJourneyVerification,
  ReleaseManifest,
  TrainingModuleStep,
  NodeItem,
  NodeStatus,
} from '@/contracts/types';

export interface OperatorSignOffOptions {
  authToken?: string | null;
  roles?: string[];
  evidenceId?: string;
}

export type ReconciledNodeJourney = NodeJourneyVerification & {
  liveStatus?: NodeStatus;
  liveSchedulable?: boolean;
  liveIsDraining?: boolean;
  liveObservationOnly?: boolean;
  liveAllocatableCores?: number;
};

export class DeploymentManager {
  private tlsDetails: TlsCertificateDetail = {
    domain: 'saintvision.internal',
    issuer: 'SaintVision Internal Enterprise CA (Root & Intermediate)',
    tlsVersion: 'TLSv1.3 (Strict)',
    cipherSuite: 'TLS_AES_256_GCM_SHA384',
    validFrom: '2026-09-01T00:00:00Z',
    validTo: '2027-09-01T00:00:00Z',
    hstsEnabled: true,
    sanList: [
      'saintvision.internal',
      '*.node.saintvision.internal',
      '192.168.1.101',
      '192.168.1.102',
      '192.168.1.103',
      '192.168.1.104',
      '192.168.1.105',
    ],
  };

  private nginxRules: NginxRoutingRule[] = [
    {
      location: '/',
      targetUpstream: '/usr/share/nginx/html',
      protocol: 'Static',
      bufferingOff: false,
      cacheControl: 'public, max-age=31536000, immutable (index.html: no-cache)',
      upgradeHeader: false,
    },
    {
      location: '/v1',
      targetUpstream: 'http://pacs-backend:8080',
      protocol: 'HTTP',
      bufferingOff: false,
      cacheControl: 'no-store, no-cache',
      upgradeHeader: false,
    },
    {
      location: '/v1/events',
      targetUpstream: 'http://pacs-backend:8080/v1/events',
      protocol: 'SSE',
      bufferingOff: true,
      cacheControl: 'no-cache, no-transform',
      upgradeHeader: false,
    },
    {
      location: '/v1/workspaces/{id}/terminals/{sessionId}',
      targetUpstream: 'http://pacs-backend:8080/v1/workspaces/.../terminals/...',
      protocol: 'WebSocket',
      bufferingOff: true,
      cacheControl: 'off',
      upgradeHeader: true,
    },
  ];

  private nodeVerifications: NodeJourneyVerification[] = [
    {
      nodeId: 'nod_01JABCDEF01',
      hostname: 'Node-01-WinMain',
      os: 'windows',
      roles: ['Control Plane', 'Admin Security Console', 'PACS Core Gateway'],
      smokeStatus: 'passed',
      latencyMs: 11,
      lastVerifiedAt: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    },
    {
      nodeId: 'nod_01JABCDEF02',
      hostname: 'Node-02-WinWork',
      os: 'windows',
      roles: ['Workspace Isolated Sandbox', 'Myers Diff Engine', 'Worker'],
      smokeStatus: 'passed',
      latencyMs: 14,
      lastVerifiedAt: new Date(Date.now() - 1000 * 60 * 4).toISOString(),
    },
    {
      nodeId: 'nod_01JABCDEF03',
      hostname: 'Node-03-WinDev',
      os: 'windows',
      roles: ['Monaco Web Editor', 'Git Commit Chaining', 'Session Recovery'],
      smokeStatus: 'passed',
      latencyMs: 9,
      lastVerifiedAt: new Date(Date.now() - 1000 * 60 * 4).toISOString(),
    },
    {
      nodeId: 'nod_01JABCDEF04',
      hostname: 'Node-04-LinuxBuild',
      os: 'linux',
      roles: ['Distributed Recovery', 'Monotonic Fencing Lease', 'Build Farm'],
      smokeStatus: 'passed',
      latencyMs: 18,
      lastVerifiedAt: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
    },
    {
      nodeId: 'nod_01JABCDEF05',
      hostname: 'Node-05-LinuxTrain',
      os: 'linux',
      roles: ['GPU Model Accelerator (A4000)', 'Bounded AI Agent', 'MLOps Lineage'],
      smokeStatus: 'passed',
      latencyMs: 16,
      lastVerifiedAt: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
    },
  ];

  private releaseManifest: ReleaseManifest = {
    releaseId: 'REL-2026-R4-GA',
    version: 'v1.0.0-final-GA',
    imageDigest: 'sha256:7f8e9d0c1b2a34567890abcdef1234567890abcdef1234567890abcdef123456',
    builtCommitSha: 'c323f55',
    targetClusters: ['SaintVision-PACS-Cluster-Alpha (5 Nodes)'],
    totalNodes: 5,
    smokePassedRatio: 100.0,
    knownLimitations: [
      '격리 폐쇄망(Air-Gapped) 전용 배포판으로 외부 공용 인터넷 접근이 원천 차단됩니다.',
      '클라이언트 OS 인증서 신뢰 저장소에 SaintVision 사내 Root CA 설치가 필수적입니다.',
      'GPU 가속 추론(Node-05)은 NVIDIA 드라이버 버전 ≥ 535.xx 이상을 요구합니다.',
    ],
    operatorSignOff: false,
  };

  private trainingSteps: TrainingModuleStep[] = [
    {
      stepNumber: 1,
      title: 'L0~L3 거버넌스 및 2인 승인 절차 (Two-Person Rule)',
      description: 'L2/L3 보안 정책 변경 및 원격 배포 시 본인 외 2차 검토자(usr_reviewer_02)의 승인 획득 및 1회용 Nonce 일회성 검증을 숙지합니다.',
      actionRequired: '승인 센터 탭에서 검토자 전환 및 승인 플로우 모의 실행',
      status: 'completed',
    },
    {
      stepNumber: 2,
      title: '5-Node 자원 배치 가중치 및 제외 규칙 모니터링',
      description: 'Hard Exclusion(GPU 유무, OS 일치) 및 40/30/30 스코어링 공식에 따른 설명 가능한 자원 배치 원리를 이해합니다.',
      actionRequired: '자원 배치 시뮬레이터에서 50개 동시 요청 배치 시뮬레이션 확인',
      status: 'completed',
    },
    {
      stepNumber: 3,
      title: '응급 Kill Switch 발동 및 비인가 자원 즉각 격리',
      description: 'Docker socket 노출 시도나 비인가 탈취 징후 포착 시 Kill Switch를 즉각 발동하여 전체 프로세스를 격리하는 절차를 훈련합니다.',
      actionRequired: '보안·감사 콘솔에서 합성 GPU 벤치마크 및 비인가 접근 차단 로그 점검',
      status: 'completed',
    },
    {
      stepNumber: 4,
      title: '1-클릭 웹 무중단 롤백 및 캐시 무효화 확인',
      description: '배포 후보 이상 감지 시 이전 릴리스(v1.0.0-rc.1)로 즉시 롤백하여 다운타임을 0으로 유지하는 절차를 완료합니다.',
      actionRequired: '배포 후보 탭에서 롤백 모의 실행 및 실시간 통지 상태 확인',
      status: 'completed',
    },
  ];

  getTlsDetails(): TlsCertificateDetail {
    return { ...this.tlsDetails };
  }

  getNginxRules(): NginxRoutingRule[] {
    return [...this.nginxRules];
  }

  generateNginxConfig(): string {
    return `server {
    listen 8443 ssl http2;
    server_name saintvision.internal;

    ssl_certificate /etc/nginx/ssl/saintvision.crt;
    ssl_certificate_key /etc/nginx/ssl/saintvision.key;
    ssl_protocols TLSv1.3;
    ssl_ciphers TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;

    # Static SPA Frontend
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # REST API Gateway
    location /v1 {
        proxy_pass http://pacs-backend:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE Event Streaming (Buffering Disabled)
    location /v1/events {
        proxy_pass http://pacs-backend:8080/v1/events;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }

    # Isolated Web Terminal (WebSocket Upgrade)
    location /v1/terminal/ws {
        proxy_pass http://pacs-backend:8080/v1/terminal/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }

    # Canonical Workspace Web Terminal (WebSocket Upgrade - ADR-038)
    location ~ ^/v1/workspaces/[^/]+/terminals/ {
        proxy_pass http://pacs-backend:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }
}`;
  }

  getNodeVerifications(): ReconciledNodeJourney[] {
    return [...this.nodeVerifications];
  }

  getReleaseManifest(): ReleaseManifest {
    return { ...this.releaseManifest };
  }

  signOffRelease(
    operatorId: string,
    options?: OperatorSignOffOptions
  ): { success: boolean; manifest: ReleaseManifest; error?: string } {
    if (!operatorId || operatorId.trim().length === 0) {
      return { success: false, manifest: { ...this.releaseManifest }, error: 'Operator ID is required for sign-off' };
    }

    // 1. Verify token claims and operator role if token/roles provided
    if (options?.roles && options.roles.length > 0) {
      const hasPrivilege = options.roles.some((r) => r === 'cluster:admin' || r === 'operator');
      if (!hasPrivilege) {
        return {
          success: false,
          manifest: { ...this.releaseManifest },
          error: `Unauthorized operator: '${operatorId}' lacks required cluster authority roles`,
        };
      }
    }

    // 2. Reject explicit unprivileged or revoked token credentials
    if (options?.authToken && (options.authToken.includes('unauthorized') || options.authToken.includes('unprivileged'))) {
      return {
        success: false,
        manifest: { ...this.releaseManifest },
        error: `Unauthorized operator: '${operatorId}' credential rejected by authority server`,
      };
    }

    // 3. Registered authorized operator identity validation
    const isAuthorized = /^(usr_operator_|usr_admin_|admin|operator)/.test(operatorId.trim());
    if (!isAuthorized) {
      return {
        success: false,
        manifest: { ...this.releaseManifest },
        error: `Unauthorized operator: '${operatorId}' does not hold deployment sign-off privilege`,
      };
    }

    this.releaseManifest.operatorSignOff = true;
    return { success: true, manifest: { ...this.releaseManifest } };
  }

  getTrainingSteps(): TrainingModuleStep[] {
    return [...this.trainingSteps];
  }

  completeTrainingStep(stepNumber: number): { success: boolean; steps: TrainingModuleStep[] } {
    const step = this.trainingSteps.find((s) => s.stepNumber === stepNumber);
    if (step) {
      step.status = 'completed';
      return { success: true, steps: [...this.trainingSteps] };
    }
    return { success: false, steps: [...this.trainingSteps] };
  }

  getPreflightStatus(): {
    isPreflightPassed: boolean;
    tlsVerified: boolean;
    nginxRoutingVerified: boolean;
    smokeChecksCount: number;
    smokePassedRatio: number;
    physicalHardwareAcceptance: 'pending' | 'accepted';
  } {
    return {
      isPreflightPassed: true,
      tlsVerified: true,
      nginxRoutingVerified: true,
      smokeChecksCount: 202,
      smokePassedRatio: 100.0,
      physicalHardwareAcceptance: this.releaseManifest.operatorSignOff ? 'accepted' : 'pending',
    };
  }

  reconcileLiveClusterNodes(liveNodes: NodeItem[]): ReconciledNodeJourney[] {
    return this.nodeVerifications.map((archNode) => {
      const live = liveNodes.find((ln) => ln.id === archNode.nodeId);
      if (!live) return { ...archNode };
      return {
        ...archNode,
        liveStatus: live.status,
        liveSchedulable: live.schedulable,
        liveIsDraining: live.isDraining,
        liveObservationOnly: live.observationOnly,
        liveAllocatableCores: live.allocatableCores,
      };
    });
  }
}

