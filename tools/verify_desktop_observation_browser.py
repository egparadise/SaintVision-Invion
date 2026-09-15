"""Real Chromium UI test with intercepted HTTP fixtures; no live backend/SSO claim.
Start apps/web Vite at 127.0.0.1:5187 before running. Creates/removes a temporary harness.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:5187"

async def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix="desktop-proof-", dir=ROOT / "apps/web") as directory:
        path = Path(directory)
        (path / "index.html").write_text('<div id="root"></div><script type="module" src="./main.tsx"></script>', encoding="utf-8")
        (path / "main.tsx").write_text("""import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ModelStudioView} from '/src/features/desktop/ModelStudioView';
import {InvFileExplorer} from '/src/features/desktop/InvFileExplorer';
function Harness(){const [project,setProject]=useState('project-a'); return <><button onClick={()=>setProject('project-b')}>Switch project</button><ModelStudioView projectId={project}/><InvFileExplorer/></>}
createRoot(document.getElementById('root')!).render(<Harness/>);""", encoding="utf-8")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, channel="msedge")
            page = await browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            requests = []
            held = []
            delay_models = False
            async def intercept(route):
                request = route.request
                requests.append({"method":request.method,"url":request.url})
                if '/commitment' in request.url:
                    if delay_models:
                        held.append(route)
                        return
                    project = request.url.split('/projects/')[1].split('/')[0]
                    body = {"projectId":project,"modelId":"model-a","version":"v1","committed":True,"currentAvailability":"unknown","requiresExecutionRevalidation":True,"committedAt":"2026-09-15T00:00:00Z","manifestHash":"recorded-hash","sourceRunId":"run-a","format":"safetensors","totalBytes":10,"shardCount":1,"licensePolicy":"internal","classification":"internal"}
                elif '/locations?' in request.url:
                    body = {"items":[],"nextCursor":None}
                else:
                    await route.fulfill(status=403,json={"title":"Denied","status":403})
                    return
                await route.fulfill(json=body)
            await page.route('**/v1/**',intercept)
            await page.goto(BASE + '/' + path.name + '/index.html')
            await expect(page.get_by_text('등록된 파일이 없습니다.')).to_be_visible()
            checks.append('empty catalog renders without sample data')
            await page.get_by_label('모델 ID',exact=True).fill('model-a')
            await page.get_by_label('버전',exact=True).fill('v1')
            await page.get_by_role('button',name='기록 조회',exact=True).click()
            await expect(page.get_by_text('현재 가용성: 미확인 · 실행 시 재검증 필요')).to_be_visible()
            checks.append('GET observation displays historical result with unknown availability')
            delay_models = True
            await page.get_by_role('button',name='기록 조회',exact=True).click()
            await expect(page.get_by_text('조회 중…',exact=True)).to_be_visible()
            while not held:
                await asyncio.sleep(.01)
            await page.get_by_label('모델 ID',exact=True).fill('model-b')
            try:
                await held.pop().fulfill(json={"projectId":"project-a","modelId":"model-a","version":"v1","committed":True,"currentAvailability":"unknown","requiresExecutionRevalidation":True,"manifestHash":"stale-input-hash"})
            except Exception:
                pass  # Chromium may already have canceled the held request.
            await page.wait_for_timeout(100)
            await expect(page.get_by_text('stale-input-hash',exact=False)).to_have_count(0)
            checks.append('input change cancels/ignores previous response')
            await page.get_by_role('button',name='기록 조회',exact=True).click()
            while not held:
                await asyncio.sleep(.01)
            await page.get_by_role('button',name='Switch project').click()
            try:
                await held.pop().fulfill(json={"projectId":"project-a","modelId":"model-b","version":"v1","committed":True,"currentAvailability":"unknown","requiresExecutionRevalidation":True,"manifestHash":"stale-project-hash"})
            except Exception:
                pass
            await page.wait_for_timeout(100)
            await expect(page.get_by_label('모델 ID',exact=True)).to_have_value('')
            await expect(page.get_by_text('stale-project-hash',exact=False)).to_have_count(0)
            checks.append('project switch resets inputs and ignores previous response')
            await page.get_by_label('파일 URI',exact=True).fill('inv://private/file')
            await page.get_by_role('button',name='조회',exact=True).click()
            await expect(page.get_by_role('alert')).to_contain_text('파일을 조회할 수 없습니다')
            checks.append('denied URI displays an error without fabricated success')
            assert requests and all(item['method']=='GET' for item in requests)
            assert not errors, errors
            checks.append('all fixture HTTP requests are GET; no browser exceptions')
            await page.goto(BASE)
            await expect(page.get_by_role('button', name='Web Desktop으로 전환')).to_have_count(0)
            checks.append('unauthenticated portal does not expose Desktop entry')
            evidence = ROOT/'docs/vault/30_Development/Evidence/vf-desktop-integration'
            evidence.mkdir(parents=True,exist_ok=True)
            (evidence/'browser.json').write_text(json.dumps({"environment":"local Vite + headless Chromium; intercepted fixture HTTP, not live backend", "checks":checks,"passed":len(checks),"pageErrors":errors},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            await browser.close()
    print(json.dumps({"passed":len(checks),"checks":checks},ensure_ascii=True))

if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), timeout=60))
