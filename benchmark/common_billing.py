"""Read-only OpenRouter receipt enrichment; never issues inference or edits traces."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import http.client
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import quote
from benchmark.costs import costs_from_events
from benchmark.run import load_key,read_events,write_json

LOCAL=threading.local()


def fetch_receipt(generation_id,key):
    for attempt in range(3):
        try:
            if not getattr(LOCAL,'connection',None):LOCAL.connection=http.client.HTTPSConnection('openrouter.ai',timeout=30)
            LOCAL.connection.request('GET','/api/v1/generation?id='+quote(generation_id,safe=''),headers={'Authorization':'Bearer '+key})
            response=LOCAL.connection.getresponse();body=json.loads(response.read())
            if response.status==200:
                data=body.get('data',{});result={k:data[k] for k in ('is_byok','total_cost','upstream_inference_cost') if k in data}
                if type(result.get('is_byok')) is bool and isinstance(result.get('total_cost'),(int,float)) and not isinstance(result['total_cost'],bool):return result
                return {'billing_error':'Incomplete generation billing metadata'}
            if response.status not in (408,429,500,502,503,504):return {'billing_error_http_status':response.status}
        except (OSError,http.client.HTTPException,ValueError):pass
        if getattr(LOCAL,'connection',None):LOCAL.connection.close();LOCAL.connection=None
        if attempt<2:time.sleep(2**attempt)
    return {'billing_error':'Metadata unavailable after controlled read-only retries'}


def enrich(output,concurrency=16,completed_only=False):
    output=Path(output);manifest=json.loads((output/'manifest.json').read_text())
    if manifest['policy']!='openrouter':raise ValueError('Offline fixture data cannot claim inference billing')
    load_key();key=os.environ['OPENROUTER_API_KEY'];cache_path=output/'private-generation-billing.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
    sources={};ids=set()
    for job in manifest['repeat_schedule']:
        path=output/'episodes'/(job['episode_id']+'.jsonl')
        if not path.exists():continue
        if completed_only and manifest['phase']!='preflight':
            with path.open('rb') as stream:stream.seek(max(0,path.stat().st_size-16384));tail=stream.read()
            if not tail.endswith(b'\n'):continue
            try:last=json.loads(tail.splitlines()[-1])
            except ValueError:continue
            if last.get('event')!='episode_end':continue
        events=read_events(path);sources[path]=events
        for row in events:
            raw=row.get('raw_response',{})
            if row.get('event')=='request_result' and isinstance(raw,dict) and isinstance(raw.get('id'),str):ids.add(raw['id'])
    missing=[rid for rid in ids if rid not in cache or 'is_byok' not in cache[rid]]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures={pool.submit(fetch_receipt,rid,key):rid for rid in missing}
        for index,future in enumerate(as_completed(futures),1):
            cache[futures[future]]=future.result()
            if index%100==0:write_json(cache_path,cache);print(json.dumps(dict(billing_reads=index,requested=len(missing))),flush=True)
    write_json(cache_path,cache);rows=[]
    for path,events in sources.items():
        enriched=[]
        for original in events:
            row=dict(original);raw=row.get('raw_response',{})
            if row['event']=='request_result' and isinstance(raw,dict) and raw.get('id') in cache:row['billing_receipt']=cache[raw['id']]
            enriched.append(row)
        ended=path.with_suffix('.preflight.json').exists() if manifest['phase']=='preflight' else any(r['event']=='episode_end' for r in events)
        cost=costs_from_events(enriched,episode_id=path.stem,scope_complete=ended)
        proof=dict(schema_version=1,id=path.stem,episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cost_source='captured native receipts and read-only OpenRouter generation metadata',**cost)
        write_json(path.with_suffix('.cost.json'),proof);rows.append(proof)
    report=dict(schema_version=1,cases=len(rows),billing_ids=len(ids),actual_complete=sum(r['cost_usd'] is not None for r in rows),estimated_complete=sum(r['cost_estimate_usd'] is not None for r in rows),unknown=sum(r['cost_usd'] is None and r['cost_estimate_usd'] is None for r in rows),runs={r['id']:r for r in rows})
    write_json(output/'costs.json',report);print(json.dumps({k:v for k,v in report.items() if k!='runs'},indent=2));return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--concurrency',type=int,default=16);p.add_argument('--completed-only',action='store_true');a=p.parse_args()
    if not 1<=a.concurrency<=64:p.error('Use1..64 read-only metadata workers')
    enrich(a.output,a.concurrency,a.completed_only)

if __name__=='__main__':main()
