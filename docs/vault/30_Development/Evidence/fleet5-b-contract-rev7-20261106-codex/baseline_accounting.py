"""Stream old immutable ledger; account every old call and transaction backlog."""
import hashlib,json
from collections import Counter
from pathlib import Path
from normalized import rows
E=Path(__file__).resolve().parent

class StreamArray:
    def __init__(self,path):self.f=path.open('rb');self.buf='';self.pos=0;self.eof=False;self.decoder=json.JSONDecoder()
    def fill(self):
        raw=self.f.read(1<<20)
        if not raw:self.eof=True;return False
        self.buf=self.buf[self.pos:]+raw.decode('ascii');self.pos=0;return True
    def find(self,token):
        while True:
            at=self.buf.find(token,self.pos)
            if at>=0:self.pos=at+len(token);return
            self.pos=max(self.pos,len(self.buf)-len(token))
            if not self.fill():raise ValueError('missing key')
    def items(self):
        while True:
            while self.pos>=len(self.buf) and self.fill():pass
            ch=self.buf[self.pos]
            if ch==',':self.pos+=1;continue
            if ch==']':return
            while True:
                try:row,end=self.decoder.raw_decode(self.buf,self.pos);self.pos=end;break
                except json.JSONDecodeError:
                    if not self.fill():raise
            yield row
            if self.pos>4<<20:self.buf=self.buf[self.pos:];self.pos=0

def key(r):return tuple(r[k] for k in ('path','function','line','column','spelling'))
def main():
    old=E.parent/'fleet5-b-contract-rev6-20261106-codex/source-analysis.json';h=hashlib.sha256();size=0
    with old.open('rb') as f:
        while raw:=f.read(1<<20):h.update(raw);size+=len(raw)
    assert size==74373915 and h.hexdigest()=='19944f326147bf0d83784534231de8434eab5268355fb796f3239772f8d6ae9d'
    stream=StreamArray(old);stream.find('"classifiedCalls":[');old_calls={};backlog=set();transactions=set()
    try:
        for row in stream.items():
            k=key(row);old_calls[k]=row['classification']
            if row['classification']=='NONAUTHORITY_UNRESOLVED_EXTERNAL_BACKLOG':
                backlog.add(k)
                if row['method'] in ('transaction','begin','begin_nested'):transactions.add(k)
    finally:stream.f.close()
    assert len(old_calls)==47608 and len(backlog)==29573 and len(transactions)==107
    seen=set();delta=Counter();all_delta=Counter();tx=[]
    for row in rows('classifiedCalls'):
        k=key(row);assert k not in seen;seen.add(k);prior=old_calls.get(k,'NEW_SOURCE_CALL')
        all_delta[(prior,row['classification'])]+=1
        if k in backlog:delta[row['classification']]+=1
        if k in transactions:tx.append({k:row[k] for k in ('id','path','function','line','column','spelling','receiverType','possibleReceiverTypes','classification','targets','blocksGrant')})
    missing=set(old_calls)-seen;assert not missing
    result={'priorCommit':'ee97c27a5d135a4059256124290731cd2b791193','priorBytes':size,'priorSHA256':h.hexdigest(),
      'oldCalls':len(old_calls),'newCalls':len(seen),'oldUnprovenBacklog':len(backlog),'oldBacklogCurrentClasses':dict(delta),
      'oldTransactionBacklog':len(transactions),'currentTransactionBacklogInventory':tx,'missingOldCalls':len(missing),
      'allClassDeltas':[{'old':a,'new':b,'count':n} for (a,b),n in sorted(all_delta.items())],
      'waivers':0,'newCountsAreNotAcceptanceTargets':True,
      'scope':'Every UNRESOLVED/SQL issue remains HOLD for the causal named grant; no global runtime denial and no unreachability exemption. ALL old107 transaction sites inventoried, including still-unresolved named ports.',
      'actualRuntimeB':0}
    (E/'baseline-class-accounting.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'oldCalls':len(old_calls),'newCalls':len(seen),'oldUnproven':len(backlog),'currentClassesOfOldBacklog':dict(delta),'oldTransactions':len(tx),'missing':len(missing)}))

if __name__=='__main__':main()
