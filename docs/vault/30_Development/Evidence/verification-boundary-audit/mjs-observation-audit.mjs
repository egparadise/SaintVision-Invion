// Offline counterexamples against actual runner bodies. No network or devices.
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
import path from 'node:path';
const [root, output] = process.argv.slice(2);
const base = 'run_synthetic_new_dispatch';
const receipt = { receiptId:'rcp_01JSHARD_03', runId:'UNRELATED_RUN', nodeId:'UNRELATED_NODE', exitCode:0, physicallyStopped:true, verified:true, resourceReclaimed:true, output:{sha256:'sha256:not-a-digest'} };
const contrast = {...receipt,receiptId:'rcp_01JFAILED_VERIFY',verified:false,resourceReclaimed:false};
const nodes = [1,2,3,4,5].map(n=>({nodeId:`nod_01JABCDEF0${n}`,cpuCores:n===1?16:12,cpuUsagePercent:20}));
const shards = [1,2].map(n=>({shardId:`shard${n}`,nodeId:'UNRELATED_NODE',parentId:'run_01JPARENT_ACTIVE',attempt:1,receiptId:'UNRELATED_RECEIPT',outputHash:'sha256:not-a-digest',physicallyStopped:true,verified:true}));
async function audit(file, breakStop=false) {
  const calls=[], logs=[], exits=[];
  const fetch = async (url, options={}) => {
    const pathname=new URL(url).pathname; calls.push({path:pathname,method:options.method||'GET'});
    let status=200, body={};
    if(pathname==='/v1/health') body={};
    else if(pathname==='/v1/auth/token')body={access_token:'SYNTHETIC_TOKEN'};
    else if(pathname==='/v1/auth/userinfo')body={roles:['cluster:admin']};
    else if(pathname==='/v1/projects')body={total:2,items:[{id:'prj_01JABCDE',budgetKrw:1},{id:'prj_saint_mlops',remainingBudgetKrw:1}]};
    else if(pathname==='/v1/workspaces')body={items:[{targetNodeId:'nod_01JABCDEF01',isolationMode:'process_sandbox'},{targetNodeId:'nod_01JABCDEF05',isolationMode:'container_isolated'}]};
    else if(pathname==='/v1/pools')body={items:[{id:'pool_01_training',nodeIds:['nod_01JABCDEF01','nod_01JABCDEF05'],totalGpus:2}]};
    else if(pathname==='/v1/nodes')body={items:nodes};
    else if(pathname.endsWith('/placement-preview'))body={selectedNodeId:'nod_01JABCDEF05'};
    else if(pathname==='/v1/projects/prj_saint_mlops/runs'){
      const req=JSON.parse(options.body);
      if(req.targetNodeId==='nod_01JABCDEF04'){status=400;body={code:'VAL-NODE-OBSERVATION-ONLY'};}
      else {status=201;body={id:base,state:'running',nodeId:'nod_01JABCDEF05',entrypoint:'synthetic',leaseId:'synthetic'};}
    }
    else if(pathname.endsWith('/artifacts/download'))body={outputHash:'sha256:not-a-digest'};
    else if(pathname.endsWith('/cancel'))body={state:'cancelled',resourceReleasePending:true};
    else if(pathname===`/v1/runs/${base}`)body={state:'cancelled'};
    else if(pathname.includes('EXHAUSTED') && pathname.endsWith('/resume/prepare')){status=400;body={code:'VAL-MAX-ATTEMPTS-EXCEEDED'};}
    else if(pathname.endsWith('/resume/prepare'))body={approvalId:'approval-synthetic',spec:{inputHash:'synthetic',boundRunVersion:2,frozenFiles:['synthetic']}};
    else if(pathname.endsWith('/resume/enqueue'))body={attempt:2,state:'running'};
    else if(pathname.endsWith('/capacity'))body={totalCores:28,totalMemoryBytes:96*1024**3,gpuModels:['NVIDIA RTX 4090','NVIDIA A4000']};
    else if(pathname.endsWith('/shards'))body={items:shards};
    else if(pathname.endsWith('/cancel-all'))body={resourceReleasePending:true};
    else if(pathname.endsWith('/reclaim-resources'))body={resourceReleasePending:false,allPhysicallyStopped:!breakStop};
    else if(pathname==='/v1/receipts/rcp_01JSHARD_03')body=receipt;
    else if(pathname==='/v1/receipts/rcp_01JFAILED_VERIFY')body=contrast;
    else if(pathname==='/v1/receipts')body={total:3,items:[receipt,contrast,{}]};
    else if(pathname==='/v1/approvals')body={items:[{riskLevel:'L3',unifiedDiff:'synthetic',nonce:'abcdefghijklmnop',blastRadius:'workspace_isolated'}]};
    else if(pathname==='/v1/approvals/approval-synthetic')body={boundRunVersion:2,unifiedDiff:'frozen_manifest_hash'};
    else if(pathname.endsWith('/resume'))body={inputHash:'sha256:not-a-digest'};
    else if(pathname==='/v1/runs/run_01JPARENT_ACTIVE')body={childRunIds:['a','b']};
    else if(pathname==='/v1/runs/run_01JPARENT_SUCCESS')body={manifestDigest:'sha256:not-a-digest',allPhysicallyStopped:true,allSucceeded:true};
    else if(pathname==='/v1/runs/run_01JRECOVERING')body={attempt:1,maxAttempts:3};
    else if(pathname==='/v1/runs/run_01JRECOVERING_EXHAUSTED')body={attempt:3,maxAttempts:3};
    else if(!pathname.endsWith('/approve') && !pathname.endsWith('/reset-recovering'))throw Error('Unmapped request '+pathname);
    return {status,headers:{get:()=> 'synthetic-trace'},json:async()=>structuredClone(body)};
  };
  const original=fs.readFileSync(path.join(root,'tools',file),'utf8');
  const source=original.replace("import crypto from 'node:crypto';",'');
  const context={crypto,Buffer,fetch,console:{log:(...x)=>logs.push(x.join(' ')),error:(...x)=>logs.push(x.join(' '))},process:{env:{},exit:c=>{exits.push(c);throw Error('Captured exit '+c);}}};
  try {await vm.runInNewContext(source,context,{timeout:3000});}catch(error){if(!exits.length)throw error;}
  return {file,breakStop,scope:'fully synthetic fetch; no browser, node, GPU, DB, or network',sourceSha256:crypto.createHash('sha256').update(original).digest('hex'),passed:logs.filter(x=>x.includes('[PASS]')).length,failed:logs.filter(x=>x.includes('[FAIL]')).length,exitCode:exits.at(-1)||0,requests:calls,summary:logs.filter(x=>x.includes('Summary:')||x.includes('verified')),dispatchedRun:base,receiptRun:receipt.runId,receiptNode:receipt.nodeId,outputHash:receipt.output.sha256};
}
const results=[];
for(const file of ['verify_two_pc_distributed_execution.mjs','reconcile_receipts_evidence.mjs']){
 results.push(await audit(file));results.push(await audit(file,true));
}
fs.writeFileSync(output,JSON.stringify({scope:'counterexample evidence; not product acceptance',results},null,2)+'\n');
console.log(JSON.stringify(results.map(({file,breakStop,passed,failed,exitCode})=>({file,breakStop,passed,failed,exitCode})),null,2));
