/**
 * SaintVision Frontend & Gateway End-to-End Smoke Verification Script
 * Validates SPA index, PWA manifest, Service Worker, and proxied Control Plane API.
 */

import http from 'node:http';

async function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        resolve({
          status: res.statusCode,
          headers: res.headers,
          body: data,
        });
      });
    }).on('error', reject);
  });
}

async function runSmokeTests() {
  console.log('🚀 Running SaintVision E2E Web Smoke Checks against http://localhost:3000/...\n');
  let passed = 0;
  let total = 0;

  function assert(title, condition, extra = '') {
    total++;
    if (condition) {
      passed++;
      console.log(`  ✔ [PASS] ${title} ${extra}`);
    } else {
      console.error(`  ✖ [FAIL] ${title} ${extra}`);
    }
  }

  try {
    // 1. Root SPA HTML check
    const rootRes = await fetchUrl('http://localhost:3000/');
    assert('Root HTML served with HTTP 200', rootRes.status === 200);
    assert('Root HTML contains #root mount point', rootRes.body.includes('id="root"'));
    assert('Root HTML includes PWA manifest link', rootRes.body.includes('rel="manifest"'));

    // 2. PWA Manifest check
    const manifestRes = await fetchUrl('http://localhost:3000/manifest.json');
    assert('PWA manifest.json served with HTTP 200', manifestRes.status === 200);
    const manifest = JSON.parse(manifestRes.body.replace(/^\uFEFF/, ''));
    assert('PWA manifest name is SaintVision INV Intranet Portal', manifest.name.includes('SaintVision'));

    // 3. Service Worker check
    const swRes = await fetchUrl('http://localhost:3000/sw.js');
    assert('Service worker sw.js served with HTTP 200', swRes.status === 200);
    assert('sw.js contains cache name definition', swRes.body.includes('CACHE_NAME'));

    // 4. API Proxy /v1/health check
    const healthRes = await fetchUrl('http://localhost:3000/v1/health');
    assert('Proxied /v1/health served with HTTP 200', healthRes.status === 200);
    assert('W3C traceparent header injected', Boolean(healthRes.headers['traceparent']));
    const health = JSON.parse(healthRes.body);
    assert('Health status is healthy', health.status === 'healthy');

    // 5. API Proxy /v1/nodes check (5 nodes inventory)
    const nodesRes = await fetchUrl('http://localhost:3000/v1/nodes');
    assert('Proxied /v1/nodes served with HTTP 200', nodesRes.status === 200);
    const nodes = JSON.parse(nodesRes.body);
    assert('5 nodes enrolled in cluster', nodes.items && nodes.items.length === 5, `(found ${nodes.items?.length})`);

    // 6. RFC 9457 Problem Details error check
    const notFoundRes = await fetchUrl('http://localhost:3000/v1/nodes/nod_nonexistent');
    assert('Proxied 404 returns HTTP 404', notFoundRes.status === 404);
    assert(
      'Returns RFC 9457 application/problem+json',
      notFoundRes.headers['content-type']?.includes('application/problem+json')
    );
    const problem = JSON.parse(notFoundRes.body);
    assert('Problem contains RES-NODE-404 code', problem.code === 'RES-NODE-404');

    console.log(`\n======================================================`);
    console.log(`🎉 Smoke Verification Summary: ${passed}/${total} checks passed (100%)`);
    console.log(`======================================================\n`);

    if (passed !== total) {
      process.exit(1);
    }
  } catch (err) {
    console.error('Fatal Smoke Test Error:', err);
    process.exit(1);
  }
}

runSmokeTests();
