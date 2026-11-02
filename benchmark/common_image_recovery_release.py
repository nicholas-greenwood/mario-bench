"""Release-only audited image continuations; the original48 remain unchanged."""
from __future__ import annotations
from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import tempfile

from benchmark import common_image_recovery as R
from benchmark.common_image_recovery_results import public_manifest, project
from benchmark.common_image_final_results import aggregates
from benchmark.common_state_recovery_release import require, VERIFIED, AUDITED, ASSETS, joined_cost
from benchmark.common_state_release import attempt_evidence, sha, utc
from benchmark.client import digest
from benchmark.public_results import public_native_response
from benchmark.run import read_events,write_json
from benchmark.costs import COST_FIELDS,validate_public_cost


def validate_checkpoint(cp,original,base):
    require(cp['checkpoint_native_frame']==original['native_frames'] and cp['rng_draw_count']==original['decisions'],'Image checkpoint clock/draw count changed')
    require(cp['controller_sha256']==base['manifest']['observation_and_controller_hashes']['image_controller_sha256'],'Image controller changed')
    state=cp['rng_state'];rng=random.Random();rng.setstate((state[0],tuple(state[1]),state[2]))
    require(digest(state)==cp['rng_state_sha256'] and cp['rng_mt_index']==state[1][-1],'Full MT state/index digest differs')
    replay=random.Random(original['local_rng_seed'])
    for _ in range(original['decisions']):replay.random()
    require(R.plain(replay.getstate())==state,'Checkpoint MT state differs from original seed and committed draws')
    require(digest(cp['session_controls'])==cp['session_controls_sha256'] and len(cp['session_controls'])<=2 and len(cp['previous_images'])<=1,'Image/control history digest or bounded memory differs')
    require(cp['rng_mode']=='global_full12_temperature_sampling','Image sampler mode changed')


def normalise(base,overlay,proof_documents,prefix_raw):
    """Validate public lineage and return48 logical slots, never49 trials."""
    header=overlay['manifest'];protocol=header['protocol_sha256'];prefix=json.loads(prefix_raw)
    require(hashlib.sha256(prefix_raw).hexdigest()==header['prefix_proof_sha256'] and prefix['verified'] is True,'Independent prefix proof bytes differ')
    require(base['manifest']['protocol_sha256']==header['parent_protocol_sha256']==prefix['parent_protocol_sha256']==R.PARENT_PROTOCOL_SHA256,'Wrong original48 authority')
    originals={t['id']:t for t in base['trials']};jobs={j['episode_id']:j for j in base['manifest']['repeat_schedule']}
    require(len(originals)==len(base['trials'])==48 and set(originals)==set(jobs),'Original48 schedule/denominator changed')
    require(prefix['source_log_sha256']=={k:t['attempt_proof']['source_episode_sha256'] for k,t in originals.items()},'Independent original48 source bytes differ')
    require(base['release_provenance']['source_manifest_sha256']==header['parent_manifest_file_sha256'],'Original manifest-byte binding differs')
    require(header['acceptance_mode']=='same_checkpoint_technical_recovery_v1' and header['phase']=='technical_recovery' and header['preregistered'] is True
            and header['native_frame_budget']==header['native_frame_cap']==6000 and header['cadence_native_frames']==header['requested_native_hold']==7
            and header['life_budget']==header['max_continuations_per_slot']==1 and header['temperature']==.05,'Image recovery envelope changed')
    slots=header['slots'];eligible={k for k,t in originals.items() if not t['rankable']}
    require(slots==prefix['slots'] and len(slots)==len(eligible) and {s['original_trial_id'] for s in slots}==eligible
            and len({s['child_run_id'] for s in slots})==len(slots),'Recover all and only declared technical slots once')
    pairs={p['model_id']:p for p in base['manifest']['eligible_model_provider_pairs']};bychild={}
    for slot in slots:
        original=originals[slot['original_trial_id']];cp=slot['checkpoint'];proof=original['attempt_proof'];pair=pairs[slot['model_id']]
        require(original['status']=='infra_error' and original['technical_pending'] is True and not original['flag_get'] and not original['death']
                and original['native_replay_verified'] is True,'Never rerun a valid native death/budget/flag')
        require(slot['child_run_id']==original['id']+'--image-technical-recovery-v1' and slot['parent_episode_sha256']==proof['source_episode_sha256'],'Parent/child source identity differs')
        require(all(slot[k]==original[k] for k in ('model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed')) and slot['track']=='image','Original condition/seed/pin slot changed')
        require(slot['parent_http_attempts']==proof['request_intent_count'] and slot['parent_valid_native_actions']==slot['failed_decision_index']==original['decisions']
                and slot['remaining_native_frame_budget']==6000-original['native_frames'] and utc(proof['terminal_at_utc'])<=utc(header['frozen_at_utc']),'Original ledger/native budget changed')
        pin={k:deepcopy(pair[k]) for k in R.PIN_KEYS if k!='id'};pin['id']=slot['model_id']
        require(slot['pin_payload']==pin and digest(pin)==cp['pin_sha256'],'Image provider pin payload differs')
        validate_checkpoint(cp,original,base);bychild[slot['child_run_id']]=slot
    children={};effective=deepcopy(originals)
    for child in overlay['continuations']:
        cid=child['id'];require(cid in bychild and cid not in children,'Unexpected/duplicate image continuation');slot=bychild[cid];original=originals[slot['original_trial_id']]
        raw=proof_documents[cid];proof=json.loads(raw)
        require(hashlib.sha256(raw).hexdigest()==child['proof_sha256']==child['attempt_proof']['native_audit_sha256'],'Actual child proof bytes differ')
        require(proof['verified'] is True and all(proof[k] is True for k in VERIFIED) and proof['no_observed_valid_choice_discarded'] is True,'Native body/pin/history/MT/budget proof incomplete')
        require(proof['result'].get('id')==proof['result'].get('episode_id')==cid and proof['result'].get('record_kind')=='technical_continuation'
                and all(k in proof['result'] and child.get(k)==proof['result'][k] for k in AUDITED),'Child grade differs from exact native proof.result')
        require(child['record_kind']=='technical_continuation' and child['phase']=='technical_recovery' and child['protocol_sha256']==protocol
                and child['parent_protocol_sha256']==R.PARENT_PROTOCOL_SHA256 and child['resolves_original_trial_id']==original['id']
                and all(child[k]==slot[k] for k in ('model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed')),'Child execution authority/condition differs')
        require(proof['original_trial_id']==original['id'] and proof['child_run_id']==cid and proof['parent_protocol_sha256']==R.PARENT_PROTOCOL_SHA256
                and proof['recovery_protocol_sha256']==protocol and proof['parent_episode_sha256']==child['parent_episode_sha256']==slot['parent_episode_sha256']
                and proof['child_episode_sha256']==child['attempt_proof']['source_episode_sha256'],'Actual child/parent source bytes differ')
        require(child['checkpoint']==child['reconstructed_checkpoint']==proof['declared_checkpoint']==proof['reconstructed_checkpoint']==slot['checkpoint'],'Nested PNG/control/fullMT checkpoint differs')
        require(utc(child['started_at_utc'])>=utc(header['frozen_at_utc']) and child['native_replay_verified'] is True,'Child predates registration or lacks native audit')
        counters=('original_attempt_count','recovery_attempt_count','joined_attempt_count','original_request_result_count','recovery_request_result_count','joined_request_result_count',
                  'original_error_attempt_count','recovery_error_attempt_count','joined_error_attempt_count','original_unanswered_attempt_count','recovery_unanswered_attempt_count','joined_unanswered_attempt_count',
                  'provider_outcome_unknown_attempt_count','new_provider_outcome_unknown_attempt_count','total_provider_outcome_unknown_attempt_count','inherited_parent_valid_choice_count')
        require(all(type(proof.get(k)) is int and proof[k]>=0 for k in counters),'Explicit nonnegative source-attempt counters required')
        inherited=proof['inherited_parent_valid_choice_count'];require(inherited==int(slot['continuation_mode']=='reuse_recorded_valid_response'),'Inherited received choice scope changed')
        for key in ('inherited_parent_valid_response_sha256','inherited_parent_receipt_id_sha256'):require(proof[key]==slot[key] and (proof[key] is not None)==bool(inherited),'Inherited receipt binding differs')
        require(proof['original_attempt_count']==slot['parent_http_attempts']==original['attempt_proof']['request_intent_count']
                and proof['original_request_result_count']==original['attempt_proof']['request_result_count']
                and proof['original_error_attempt_count']==original['attempt_proof']['error_attempt_count']
                and proof['original_unanswered_attempt_count']==original['attempt_proof']['unanswered_attempt_count'],'Original55/error/unknown scope changed')
        for suffix in ('attempt_count','request_result_count','error_attempt_count','unanswered_attempt_count'):
            require(proof['joined_'+suffix]==proof['original_'+suffix]+proof['recovery_'+suffix],'Joined source counters changed')
        require(proof['joined_attempt_count']-proof['joined_request_result_count']==proof['joined_unanswered_attempt_count']
                and proof['original_request_result_count']-proof['original_error_attempt_count']==original['decisions']+inherited
                and proof['recovery_request_result_count']-proof['recovery_error_attempt_count']+inherited==child['continuation_decisions']
                and proof['joined_request_result_count']-proof['joined_error_attempt_count']==child['decisions'],'Valid replies/actions or unmatched attempts were discarded')
        ap=child['attempt_proof'];require(ap['scope']=='composed_trajectory' and ap['request_intent_count']==proof['joined_attempt_count']
             and ap['request_result_count']==proof['joined_request_result_count'] and ap['error_attempt_count']==proof['joined_error_attempt_count']
             and ap['unanswered_attempt_count']==proof['joined_unanswered_attempt_count'],'Child attempt proof must cover composed trajectory')
        require(proof['provider_outcome_unknown_attempt_count']==slot['provider_outcome_unknown_attempt_count'] and proof['total_provider_outcome_unknown_attempt_count']==proof['provider_outcome_unknown_attempt_count']+proof['new_provider_outcome_unknown_attempt_count'],'Provider uncertainty dropped')
        require(proof['total_native_frame_budget']==child['native_frame_budget']==6000 and child['life_budget']==1 and child['cadence_native_frames']==7
                and slot['checkpoint']['checkpoint_native_frame']<=child['native_frames']==child['frames']==proof['total_native_frames']<=6000
                and child['continuation_native_frames']==proof['new_native_frames']==child['native_frames']-original['native_frames']
                and child['continuation_decisions']==child['decisions']-original['decisions'],'Native cap or original prefix reset')
        require(math.isfinite(child['max_progress_x']) and child['max_progress_x']>=original['max_progress_x'],'Whole trajectory lost original furthest progress')
        validate_public_cost(child);require(joined_cost(child,proof)=={k:child.get(k) for k in COST_FIELDS},'Logical cost is not joined or masks provider uncertainty')
        children[cid]=child
    resolved=set()
    for resolution in overlay['resolutions']:
        oid,cid=resolution['original_trial_id'],resolution['child_run_id'];require(oid not in resolved and cid in children and bychild[cid]['original_trial_id']==oid,'Duplicate/cross-slot resolution')
        child=children[cid];proof=json.loads(proof_documents[cid]);record=resolution['effective_trial']
        require(child['rankable'] is True and child['status'] in ('game_over','frame_budget','completed') and not child['technical_pending'] and proof['joined_unanswered_attempt_count']==0
                and bychild[cid]['continuation_mode']!='unanswered_no_resend','Infrastructure/unanswered continuation cannot resolve quality')
        require(resolution['parent_episode_sha256']==child['parent_episode_sha256'] and resolution['child_episode_sha256']==child['attempt_proof']['source_episode_sha256']
                and resolution['proof_sha256']==child['proof_sha256'] and resolution['proof_href']==child['proof_href'] and all(resolution[k] is True for k in VERIFIED),'Resolution lineage differs')
        require(record['id']==record['logical_trial_id']==oid and record['source_run_id']==cid and record['record_kind']=='technical_resolution'
                and record['base_protocol_sha256']==R.PARENT_PROTOCOL_SHA256 and all(record[k]==child[k] for k in AUDITED+COST_FIELDS+ASSETS),'Logical projection differs from actual child')
        effective[oid]=deepcopy(record);resolved.add(oid)
    # A scratch authority wrapper lets the unchanged image aggregate validate jobs.
    proxy={'repeat_schedule':base['manifest']['repeat_schedule']};records=list(effective.values());scratch=deepcopy(records)
    for r in scratch:r['phase']='evaluation';r['protocol_sha256']=digest(proxy)
    rows=aggregates(proxy,scratch)
    for row in rows:row['protocol_sha256']=R.PARENT_PROTOCOL_SHA256
    return dict(effective_trials=records,effective_rows=rows,resolved_slots=len(resolved),logical_trials=48)


def actions(rows,inherited_response=None):
    from collections import defaultdict
    grouped=defaultdict(list);output=[]
    for row in rows:
        if 'decision_index' in row:grouped[row['decision_index']].append(row)
    for index,records in sorted(grouped.items()):
        native=next((r for r in records if r['event']=='action'),None)
        if native is None:continue
        chunk=next(r for r in records if r['event']=='chunk_end');response=next((r for r in records if r['event']=='request_result' and r.get('valid')),None)
        if response is None:
            marker=next(r for r in records if r['event']=='inherited_valid_response')
            require(inherited_response is not None and digest(inherited_response['raw_response'])==marker['raw_response_sha256'],'Inherited action must reuse bound parent receipt')
            response=inherited_response
        output.append(dict(index=index,frame_before=native['frame_before'],frame_after=chunk['frame'],sequence=[[chunk['actual_frames'],native['buttons']]],
            requested_frames=native['requested_frames'],actual_frames=chunk['actual_frames'],request_sha256=response['request_sha256'],native_response=public_native_response(response['raw_response']),
            chosen_action={k:v for k,v in native.items() if k not in ('event','episode_id','utc')},after_observation_sha256=chunk['observation_sha256'],screen_after_sha256=chunk['screen_sha256'],native_frame_hashes=chunk['native_frame_hashes']))
    return output


def verify_public(directory):
    """Rebuild full PNG requests and every native/RNG checkpoint without keys."""
    root=Path(directory).resolve()
    def asset(href):
        path=(root/href).resolve();require(path.is_relative_to(root),'Public asset escapes release root');return path
    base=json.loads((root/'common-image/index.json').read_text())['common_benchmark'];overlay=base['technical_recovery'];header=overlay['manifest']
    require(header['software_sha256']==R.source_hashes(),'Frozen22 local source bytes differ from public recovery')
    require(R.E.actual_rom_sha256()==base['manifest']['actual_rom_sha256'],'Installed ROM differs from public protocol')
    prefix_raw=asset(header['prefix_proof_href']).read_bytes();proofs={c['id']:asset(c['proof_href']).read_bytes() for c in overlay['continuations']}
    logical=normalise(base,overlay,proofs,prefix_raw);slots={s['child_run_id']:s for s in header['slots']};pairs={p['model_id']:p for p in base['manifest']['eligible_model_provider_pairs']}
    reports=[]
    for child in overlay['continuations']:
        cid=child['id'];slot=slots[cid];trace_path=asset(child['trace_href']);require(sha(trace_path)==child['trace_sha256'],'Whole-trajectory trace bytes differ')
        trace=json.loads(trace_path.read_text());require(trace['source_episode_sha256']==child['attempt_proof']['source_episode_sha256'] and trace['attempt_proof']==child['attempt_proof'],'Public trace source/attempt binding differs')
        attempts=trace['request_attempts'];seen=set();checked=set();groups={}
        for attempt in attempts:
            key=(attempt['source_run_id'],attempt['decision_index'],attempt['stage'],attempt['attempt'])
            require(key not in seen and attempt['source_run_id'] in (slot['original_trial_id'],cid),'Duplicate/foreign public HTTP attempt');seen.add(key)
            require(type(attempt['attempt']) is int and 0<=attempt['attempt']<3 and attempt['stage']=='motor','Invalid public stage/attempt number')
            if attempt['valid']:require(type(attempt['http_status']) is int and 200<=attempt['http_status']<300 and len(attempt.get('response_id_sha256',''))==64,'Actual provider origin proof missing')
            groups.setdefault(attempt['decision_index'],[]).append(attempt)
        proof=json.loads(proofs[cid]);require(len(attempts)==proof['joined_attempt_count'] and sum(a['response_recorded'] for a in attempts)==proof['joined_request_result_count']
            and sum(a['response_recorded'] and not a['valid'] for a in attempts)==proof['joined_error_attempt_count'],'Public all-attempt census differs')
        model=dict(pairs[slot['model_id']],id=slot['model_id']);session=R.E.CommonSession(model,'image',temperature=slot['temperature'],sampler_seed=slot['local_rng_seed']);game=R.MarioGame(level='1-1');maximum=40.;history=[]
        try:
            require(digest(game.observe())==base['manifest']['initial_observation_sha256'] and R.E.screen_hash(game)==base['manifest']['initial_screen_sha256'],'Native reset differs')
            def check_body(index,body):
                require(index in groups,'No actual receipt/attempt evidence for native decision')
                for attempt in groups[index]:
                    require(attempt['request_sha256']==digest(body),'Full current/past PNG request body differs')
                    if index<slot['failed_decision_index']:require(attempt['source_run_id']==slot['original_trial_id'],'Child request before original checkpoint')
                    if index>slot['failed_decision_index']:require(attempt['source_run_id']==cid,'Original request after aborted checkpoint')
                checked.add(index)
            for index,action in enumerate(trace['actions']):
                require(not game.done and not game.flag_get and game.frame<6000 and action['index']==index and action['frame_before']==game.frame,'Extra/reset native action after terminal or budget')
                session.begin_image(R.E.rgb_png(game),frame=game.frame);body=session.body('motor');check_body(index,body)
                if index==slot['failed_decision_index']:
                    require(R.checkpoint(game,session,body,model,slot['checkpoint']['controller_sha256'],history)==slot['checkpoint'],'Public native/current-past PNG/control/fullMT prefix differs')
                require(sum(a['valid'] for a in groups[index])==1 and action['request_sha256']==digest(body),'Committed action lacks unique received valid choice')
                session.parse(action['native_response'],body);choice=session.choose(action['native_response'],body)
                expected=R.plain(dict(decision_index=index,frame_before=game.frame,observation_sha256=digest(game.observe()),**choice,frames=min(7,6000-game.frame)))
                require(action['chosen_action']==expected,'Native buttons/raw12/weights/draw/fullMT action differs')
                maximum,chunk=R.advance(game,session,choice,index,cid,maximum,history)
                require(action['frame_after']==chunk['frame'] and action['actual_frames']==chunk['actual_frames'] and action['sequence']==[[chunk['actual_frames'],choice['buttons']]]
                        and action['after_observation_sha256']==chunk['observation_sha256'] and action['screen_after_sha256']==chunk['screen_sha256']
                        and action['native_frame_hashes']==chunk['native_frame_hashes'],'Native RAM/RGB checkpoint differs')
            if child['status']=='infra_error':
                session.begin_image(R.E.rgb_png(game),frame=game.frame);body=session.body('motor');index=len(trace['actions']);check_body(index,body)
                require(not any(a['valid'] for a in groups[index]),'Valid pending choice was discarded as infrastructure')
                if index==slot['failed_decision_index']:require(R.checkpoint(game,session,body,model,slot['checkpoint']['controller_sha256'],history)==slot['checkpoint'],'Unadvanced image checkpoint differs')
            require(checked==set(groups),'Unconsumed attempt after native termination')
            status='completed' if game.flag_get else 'game_over' if game.done else 'frame_budget' if game.frame==6000 else 'infra_error'
            require(status==child['status'] and game.frame==child['native_frames'] and len(trace['actions'])==child['decisions']
                    and bool(game.flag_get)==child['flag_get'] and bool(game.death)==child['death'] and maximum==child['max_progress_x'],'Whole-prefix native outcome differs')
            reports.append(dict(id=cid,verified=True,native_frames=game.frame,decisions=len(trace['actions']),status=status,request_attempts=len(attempts)))
        finally:game.close()
    return dict(verified=True,logical_trials=48,resolved_slots=logical['resolved_slots'],children=reports)


def reused_audit(path,declared,slot,manifest):
    require(declared['episode_sha256']==sha(path) and declared['audit_sha256']==sha(path.with_suffix('.audit.json')),'Captured source/native-proof SHA differs')
    proof=json.loads(path.with_suffix('.audit.json').read_text());last=read_events(path)[-1]
    require(last['event']=='episode_end' and proof['verified'] is True and all(proof[k] is True for k in VERIFIED)
            and proof['child_episode_sha256']==declared['episode_sha256'] and proof['parent_episode_sha256']==slot['parent_episode_sha256']
            and proof['recovery_protocol_sha256']==digest(manifest) and proof['parent_protocol_sha256']==R.PARENT_PROTOCOL_SHA256,'Existing native audit has different authority/source')
    result=deepcopy(last['result']);result['native_replay_verified']=True
    require(result==proof['result'],'Existing native proof/result differs from captured terminal log')
    return proof


def export(base_directory,recovery_workspace,destination,*,reuse_audit_map=None):
    base_directory,recovery_workspace,destination=map(lambda p:Path(p).resolve(),(base_directory,recovery_workspace,destination))
    m,pm=R.verify(recovery_workspace);public_root=(destination/'common-image').resolve()
    for worker in (recovery_workspace,Path(m['parent_output']).resolve()):
        require(public_root!=worker and not public_root.is_relative_to(worker) and not worker.is_relative_to(public_root),'Never export over worker/original output')
    require(public_root/'index.json'!=base_directory/'common-image/index.json','Never overwrite the immutable original public base')
    document=json.loads((base_directory/'common-image/index.json').read_text());base=deepcopy(document)
    prior=base['common_benchmark'].pop('technical_recovery',None)
    if prior:require(prior['manifest']['protocol_sha256']==digest(m) and not prior['continuations'] and not prior['resolutions'],'Use immutable original48 or exact pending base')
    prefix_raw=Path(m['prefix_proof_path']).read_bytes();prefix=json.loads(prefix_raw);prefix_href='common-image/recovery/proofs/independent-prefix-'+m['prefix_proof_sha256']+'.json'
    require(hashlib.sha256(prefix_raw).hexdigest()==m['prefix_proof_sha256'],'Actual prefix proof bytes differ')
    output=project(base,m,prefix,prefix_href);overlay=output['common_benchmark']['technical_recovery'];proofs={};assets={prefix_href:prefix_raw};source_hashes={}
    with tempfile.TemporaryDirectory(prefix='mario-image-recovery-release-') as tmp:
        copied=Path(tmp);(copied/'episodes').mkdir();(copied/'parents').mkdir()
        for slot in m['slots']:
            cid,oid=slot['child_run_id'],slot['original_trial_id'];source=recovery_workspace/'episodes'/(cid+'.jsonl')
            if not source.exists():continue
            raw=source.read_bytes()
            if not raw.endswith(b'\n'):continue
            rows=[json.loads(line) for line in raw.splitlines() if line]
            if not rows or rows[-1]['event']!='episode_end':continue
            expected=hashlib.sha256(raw).hexdigest();target=copied/'episodes'/source.name;target.write_bytes(raw);require(sha(source)==expected,'Child changed during capture')
            parent=Path(slot['parent_episode_path']);parent_raw=parent.read_bytes();parent_copy=copied/'parents'/parent.name;parent_copy.write_bytes(parent_raw)
            require(sha(parent)==sha(parent_copy)==slot['parent_episode_sha256'],'Original parent changed during capture')
            local=deepcopy(slot);local['parent_episode_path']=str(parent_copy)
            if reuse_audit_map is None:
                result=R.execute_one(copied,m,pm,local,audit=True);source_native_audit=sha(target.with_suffix('.audit.json'));proof=json.loads(target.with_suffix('.audit.json').read_text())
            else:
                from benchmark.costs import costs_from_events
                proof=reused_audit(source,reuse_audit_map[cid],slot,m);source_native_audit=reuse_audit_map[cid]['audit_sha256']
                result=dict(proof['result'],**costs_from_events(read_events(parent_copy)+rows))
            proof['source_native_audit_sha256']=source_native_audit
            proof['result'].pop('error',None);parent_rows=read_events(parent_copy);pa,pp,pids=attempt_evidence(parent_rows);ca,cp,cids=attempt_evidence(rows)
            require(not set(pids).intersection(cids),'Parent receipt reused as new HTTP call')
            # Both actual native origins and strict returned pins/questions are mandatory.
            model=next(v for v in pm['models'] if v['id']==slot['model_id']);session=R.E.CommonSession(model,'image',temperature=slot['temperature'],sampler_seed=slot['local_rng_seed'])
            for r in rows:
                if r['event']=='request_result' and r.get('valid'):
                    intent=next(v for v in rows if v['event']=='request_intent' and all(v[k]==r[k] for k in ('decision_index','stage','attempt')))
                    require(digest(intent['body'])==r['request_sha256'],'Actual child body SHA differs');session.parse(r['raw_response'],intent['body'])
            proof_raw=(json.dumps(proof,indent=2,allow_nan=False)+'\n').encode();psha=hashlib.sha256(proof_raw).hexdigest();proof_href='common-image/recovery/proofs/'+cid+'.json';trace_href='common-image/recovery/traces/'+cid+'.json'
            original=next(t for t in base['common_benchmark']['trials'] if t['id']==oid);child=deepcopy(proof['result'])
            child.update(display_name=original['display_name'],mode='image',verified=True,returned_model=None,provider=None,actual_returned_model_provider_pairs=[],
                         profile_href=original['profile_href'],proof_href=proof_href,proof_sha256=psha,trace_href=trace_href,replay_href=None,replay_sha256=None,
                         attempt_proof=dict(scope='composed_trajectory',source_episode_sha256=expected,native_audit_sha256=psha,request_intent_count=proof['joined_attempt_count'],
                           request_result_count=proof['joined_request_result_count'],error_attempt_count=proof['joined_error_attempt_count'],unanswered_attempt_count=proof['joined_unanswered_attempt_count'],
                           started_at_utc=child['started_at_utc'],terminal_at_utc=rows[-1]['utc']),**joined_cost(result,proof))
            actual=sorted({(r['raw_response']['model'],r['raw_response']['provider']) for r in rows if r['event']=='request_result' and r.get('valid')})
            if actual:child.update(returned_model=actual[0][0],provider=actual[0][1],actual_returned_model_provider_pairs=[dict(model=a,provider=b) for a,b in actual])
            for a in pa:a['source_run_id']=oid
            for a in ca:a['source_run_id']=cid
            inherited_response=next((r for r in parent_rows if r['event']=='request_result' and r.get('valid') and r['decision_index']==slot['failed_decision_index']),None)
            prefix_actions=actions(parent_rows);suffix=actions(rows,inherited_response);tape=prefix_actions+suffix
            require(len(tape)==child['decisions'] and all(a['frame_after']==b['frame_before'] for a,b in zip(tape,tape[1:])),'Composed image trace resets or duplicates native frames')
            trace=dict(schema_version=1,id=cid,record_kind='technical_continuation',phase='technical_recovery',protocol_sha256=digest(m),parent_protocol_sha256=R.PARENT_PROTOCOL_SHA256,
                model_id=slot['model_id'],track='image',mode='image',level='1-1',resolves_original_trial_id=oid,parent_episode_sha256=slot['parent_episode_sha256'],source_episode_sha256=expected,
                actions=tape,request_attempts=pa+ca,attempt_proof=child['attempt_proof'],proof_href=proof_href,proof_sha256=psha,native_replay_verified=True)
            trace_raw=(json.dumps(trace,indent=2,allow_nan=False)+'\n').encode();child['trace_sha256']=hashlib.sha256(trace_raw).hexdigest()
            proofs[cid]=proof_raw;assets[proof_href]=proof_raw;assets[trace_href]=trace_raw;overlay['continuations'].append(child)
            if child['rankable'] and child['status'] in ('completed','game_over','frame_budget'):
                effective=deepcopy(child);effective.update(id=oid,logical_trial_id=oid,source_run_id=cid,record_kind='technical_resolution',base_protocol_sha256=R.PARENT_PROTOCOL_SHA256)
                overlay['resolutions'].append(dict(original_trial_id=oid,child_run_id=cid,parent_episode_sha256=slot['parent_episode_sha256'],child_episode_sha256=expected,proof_href=proof_href,proof_sha256=psha,
                    **{k:True for k in VERIFIED},effective_trial=effective))
            require(sha(source)==expected and sha(parent)==slot['parent_episode_sha256'],'Raw source changed during copied audit');source_hashes[cid]=expected
            if reuse_audit_map is not None:require(sha(source.with_suffix('.audit.json'))==source_native_audit,'Captured audit proof changed during projection')
    logical=normalise(base['common_benchmark'],overlay,proofs,prefix_raw)
    original=deepcopy(output);original['common_benchmark'].pop('technical_recovery');require(original==base,'Original48 data/rows must remain unchanged')
    raw=json.dumps(output)+''.join(v.decode() for v in assets.values());require(not any(t in raw for t in ('/Users/','gen-','OPENROUTER_API_KEY','sk-or-')),'Private path/credential/raw API ID in public release')
    for name,data in assets.items():path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    root=destination/'common-image';root.mkdir(parents=True,exist_ok=True);write_json(root/'index.json',output)
    return dict(continuations=len(proofs),resolutions=logical['resolved_slots'],logical_trials=48,complete_model_rows=sum(r['coverage_complete'] for r in logical['effective_rows']),source_episode_sha256=source_hashes)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path);p.add_argument('--recovery-workspace',type=Path);p.add_argument('--destination',type=Path);p.add_argument('--verify-public',type=Path)
    p.add_argument('--reuse-audit-map',type=Path,help='Explicit trusted capture map: child ID to episode_sha256 and audit_sha256; default replays copies')
    a=p.parse_args()
    if a.verify_public:value=verify_public(a.verify_public)
    else:
        p.error('--base, --recovery-workspace and --destination are required') if not all((a.base,a.recovery_workspace,a.destination)) else None
        value=export(a.base,a.recovery_workspace,a.destination,reuse_audit_map=json.loads(a.reuse_audit_map.read_text()) if a.reuse_audit_map else None)
    print(json.dumps(value,indent=2))


if __name__=='__main__':main()
