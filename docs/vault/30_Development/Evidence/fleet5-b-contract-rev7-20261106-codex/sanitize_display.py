"""Mask DSN-shaped source DISPLAY strings, preserving raw Git/hash bindings.

This uses the unchanged repository document guard's pattern. It does not read any
deployed configuration, secret, key or live DSN. Exact source is immutable72028;
coordinates and expression hashes continue referring to those ORIGINAL bytes.
Only display strings change. Every changed field/row/raw ledger hash is recorded.
"""
import hashlib,importlib.util,json
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
spec=importlib.util.spec_from_file_location('unchanged_doc_guard',ROOT/'tools/check_docs.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
    manifest_path=E/'source-manifest.json';original=manifest_path.read_bytes();manifest=json.loads(original);changes=[];inputs={}
    for key,item in manifest['ledgers'].items():
        path=E/item['file'];assert path.resolve().is_relative_to(E.resolve())
        temp=E/(item['file']+'.display-tmp');before=digest(path.read_bytes());assert before==item['sha256']
        inputs[key]=dict(item);count=0;h=hashlib.sha256();size=0
        with path.open('rb') as src,temp.open('wb') as dst:
            for raw in src:
                row=json.loads(raw);field_changes=[]
                def transform(value,pointer=''):
                    if isinstance(value,str):
                        masked=guard.PASSWORD_BEARING_POSTGRES_DSN.sub(lambda m:m.group(0).split('://',1)[0]+'://<redacted>:<redacted>@',value)
                        if masked!=value:field_changes.append({'field':pointer,'rawTextSHA256':digest(value.encode()),'displayTextSHA256':digest(masked.encode())})
                        return masked
                    if isinstance(value,list):return [transform(v,pointer+'/'+str(i)) for i,v in enumerate(value)]
                    if isinstance(value,dict):return {k:transform(v,pointer+'/'+k) for k,v in value.items()}
                    return value
                row=transform(row)
                if field_changes:
                    record={'ledger':key,'row':count,'id':row.get('id'),'rawRowSHA256':digest(raw),'fields':field_changes}
                    changes.append(record);row['displayRedaction']={'rawRowSHA256':record['rawRowSHA256'],'fields':field_changes,'sourceCoordinatesAndRawHashes':'ORIGINAL Git72028 bytes; masked display is not a replacement source'}
                encoded=(json.dumps(row,separators=(',',':'),ensure_ascii=True)+'\n').encode();dst.write(encoded);h.update(encoded);size+=len(encoded);count+=1
        assert count==item['rows'];temp.replace(path)
        item.update(bytes=size,sha256=h.hexdigest())
    ledger={'level':'DISPLAY_ONLY_MASKING','source':manifest['source'],'scriptSHA256':digest(Path(__file__).read_bytes()),
      'originalManifestSHA256':digest(original),'inputLedgers':inputs,'changedRows':changes,
      'rawSource':'Original immutable Git bytes and hashes retained; no raw credentials copied to report; actual deployment/private DSNs never read',
      'policyOrAuthorityChange':False}
    (E/'display-redaction-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf8')
    manifest['displayPostprocessing']={'script':'sanitize_display.py','scriptSHA256':ledger['scriptSHA256'],'ledger':'display-redaction-ledger.json',
       'originalManifestSHA256':ledger['originalManifestSHA256'],'changedRows':len(changes),'sourceCoordinatesAndExpressionHashes':'ORIGINAL Git bytes; display may be masked with field-level raw/display hashes'}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'displayMaskedRows':len(changes),'changedFields':sum(len(r['fields']) for r in changes),'rawSourceAndGuardUnchanged':True}))
if __name__=='__main__':main()
