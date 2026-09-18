import {execFileSync} from 'node:child_process';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=execFileSync('git',['show','bfb225e:tools/run_browser_smoke.mjs'],{encoding:'utf8'});
const helper=source.slice(source.indexOf('function recordUnverified('),source.indexOf('function base64Url('));
const tail=source.slice(source.indexOf('    // 7. Multi-window Manager'),source.indexOf('  } catch (err)'));
const results=[];
for(const [passed,total,expectedExit] of [[2,2,0],[1,2,1],[0,0,1]]) {
 const logs=[];let exit=0;
 const ctx={console:{log:(x)=>logs.push(x)},process:{exit:(x)=>{exit=x;}}};
 vm.createContext(ctx);
 vm.runInContext(`let passed=${passed},total=${total},unverified=0;`+helper+tail+';globalThis.result={passed,total,unverified};',ctx);
 assert.equal(ctx.result.passed,passed);assert.equal(ctx.result.total,total);assert.equal(ctx.result.unverified,3);assert.equal(exit,expectedExit);
 assert.equal(logs.filter(x=>x.includes('[UNVERIFIED]')).length,3);
 assert.ok(logs.some(x=>x.includes('API Contract Smoke Summary:')));
 assert.ok(!logs.some(x=>x.includes('[PASS]')||x.includes('Full E2E')));
 results.push({seed:{passed,total},result:ctx.result,exit,logs});
}
console.log(JSON.stringify({scope:'exact helper and UI/summary slice, no HTTP or full-run acceptance',results},null,2));
