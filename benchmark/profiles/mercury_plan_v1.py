"""Frozen winning Mercury pixels-only sampled duration-first development policy.
Pure inputs: lossless screenshots, prior model-chosen controls and native planner
answers. No emulator, RAM, network, environment, filesystem, detector or route.
The sampler is the frozen CASE decoder, alpha-renamed to separate action maps.
"""
import base64,io,json
from PIL import Image

def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

"""Frozen image-only probability-sampled development profile v1.

Use the existing pure image_v1.profile_request builder with BUILDER_PROFILE_ID;
substitute only the declared model/provider pins for another model. No emulator,
RAM, environment, network or credential inputs are accepted by this decoder.
"""
import math
import random
BUILDER_PROFILE_ID = 'pixels-edge-pplx-c7-v1'
PROFILE_ID = 'planning-sampled-t.2-seed0-c12-v1'
TEMPERATURE = 0.2
SEED = 0
SAMPLER_ACTIONS = {f'{d}_B_{b}_A_{a}': dict(horizontal=d, vertical='released', run=b, jump=a) for d in ['left', 'released', 'right'] for b in ['released', 'held'] for a in ['released', 'held']}

def new_rng():
    return random.Random(SEED)

def frozen_sample(raw_response, rng):
    probabilities = raw_response['answers']['action']['probabilities']
    if set(probabilities) != set(SAMPLER_ACTIONS) or any((not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0 for p in probabilities.values())) or abs(sum(probabilities.values()) - 1) >= 0.03:
        raise ValueError('Invalid complete native action probability distribution')
    keys = sorted(probabilities)
    weights = {key: probabilities[key] ** (1 / TEMPERATURE) for key in keys}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError('Zero tempered mass')
    tempered = {key: weights[key] / total for key in keys}
    before = rng.getstate()
    draw = rng.random()
    cumulative = 0.0
    selected = keys[-1]
    for key in keys:
        cumulative += tempered[key]
        if draw < cumulative:
            selected = key
            break
    return (dict(SAMPLER_ACTIONS[selected]), dict(sampled_choice=selected, random_uniform=draw, rng_state_before=before, rng_state_after=rng.getstate(), raw_probabilities=probabilities, tempered_probabilities=tempered))

CONTROL_HISTORY_RETENTION=6000

ACTIONS={f'{direction}_{speed}_{jump}':dict(horizontal=direction,vertical='released',run='held' if speed=='run' else 'released',jump='held' if jump=='jump' else 'released') for direction in ('left','released','right') for speed in ('walk','run') for jump in ('release','jump')}

RULES='''Play Super Mario Bros. World 1-1 to the flag alive. All scene evidence comes from screenshots. Each screenshot is the same fixed lower-gameplay view enlarged with nearest-neighbour pixels; all chronological views have identical framing. Parts outside this fixed view are unknown. Infer Mario, motion, solid surfaces, enemies and gaps visually. Right advances, left retreats, B runs faster and makes jumps travel farther. A starts a jump only on a fresh press while standing on a solid surface. Holding A during ascent increases jump height and length; releasing early makes a low hop. Pressing A while airborne cannot start another jump. Release A during descent to prepare the next grounded takeoff. Holding A through landing does not start another jump. Side contact with enemies and falling into gaps are dangerous. Landing on an ordinary enemy from above can stomp it. Pipes and stairs support Mario on their tops. Mario feet must rise above a solid surface before moving across its side. Ceilings interrupt ascent. Momentum persists when buttons are released. The game pauses during both planning and motor inference. Every action is chosen by you; no controller correction or route exists.
Inspect the path ahead before choosing a maneuver: an enemy can collide from the side before Mario has time to rise, and a raised solid side can stop forward travel. Infer whether the currently chosen forward movement is safe throughout the next interval. Choose a visible safe landing target and a short maneuver toward it. A target can be the current platform, the next raised surface, or ground beyond a visible gap. Keep the landing target in mind while rising and descending. Confirm that Mario actually landed before attempting a fresh jump. A small raised landing can require less forward acceleration. Avoid jumping needlessly far before a gap, which can make the descent end above the gap. These are general mechanics; infer the actual local target and takeoff timing from the pixels. Use qualitative descriptions only, without coordinates or numerical distances. Your prior plans are uncertain hypotheses, and you may revise them using the current screenshot.'''

def choice(instructions,criteria):return dict(type='choice',instructions=instructions,criteria=criteria)

PLAN_QUESTIONS={'landing_subgoal':choice('Choose your own next local destination or landing subgoal needed to advance alive. Do not merely label Mario current condition. Inspect the CURRENT screenshot first and use the labelled past views only for motion context. Select the next safe support to reach or remain on, considering visible enemies, solid sides and floor gaps. This is a qualitative uncertain visual plan; no route or surface candidates are provided externally.',{
 'advance_clear_ground':'Continue along the visible clear supported ground ahead, when no visible near obstacle or enemy requires a different immediate subgoal.',
 'land_on_next_raised_top':'Reach and land safely on the top of the next visible raised pipe, block or stair surface ahead. The feet must get above that top before crossing its side.',
 'land_on_far_side_of_gap':'Reach visible safe support beyond the nearby visible floor gap, timing takeoff so the landing reaches that support.',
 'pass_visible_enemy_safely':'Pass a nearby visible enemy without side contact, using a safe landing beyond it or a descending stomp as inferred from the pixels.',
 'finish_current_landing':'Complete the ongoing flight onto the selected visible safe support before starting a distinct new jump. Avoid drifting past a small platform.',
 'reposition_on_safe_support':'Retreat or reduce forward movement on visible safe support to create room for the next jump, or stay on a small landing while preparing the next maneuver.',
 'uncertain_reassess':'No safe visible subgoal is clear; reassess cautiously using pixels and prior chosen controls.'})}

ACTION_QUESTIONS={'action':choice('Choose ONE complete controller state for the next interval. Recheck the screenshots: the qualitative plan is your own uncertain hypothesis and never forces a button. All twelve choices remain available. Choose whether to hold or release A and whether to run or walk so that Mario reaches a safe support and progresses alive.',{name:f"Hold horizontal={v['horizontal']}, B(run)={v['run']}, A(jump)={v['jump']}; vertical released. All inputs stay constant through this interval." for name,v in ACTIONS.items()})}

DURATIONS={'precision_2':2,'precision_4':4,'routine_6':6,'sustain_12':12}

DURATION_QUESTION=choice('Choose how many native frames to hold YOUR selected complete buttons before another screenshot. You choose the timing; no automatic contact-based stopping or correction exists.',{'precision_2':'Hold chosen buttons for 2 native frames, then inspect. Fine timing near contact, a landing, enemy or fresh A edge.','precision_4':'Hold chosen buttons for 4 native frames, then inspect. Precise movement near visible hazards or a small support.','routine_6':'Hold chosen buttons for 6 native frames, then inspect. Routine progress with room.','sustain_12':'Hold chosen buttons for 12 native frames, then inspect. Sustain enough ascent, height or travel when the trajectory has safe room.'})

def sample_motor(motor,rng):
 raw=motor['action']['probabilities'];canonical_probs={}
 for label,buttons in ACTIONS.items():
  canonical_label=buttons['horizontal']+'_B_'+buttons['run']+'_A_'+buttons['jump']
  assert canonical_label not in canonical_probs
  canonical_probs[canonical_label]=raw[label]
 assert len(canonical_probs)==12
 buttons,sampling=frozen_sample({'answers':{'action':{'probabilities':canonical_probs}}},rng)
 selected=[name for name,value in ACTIONS.items() if value==buttons];assert len(selected)==1
 sampling['native_api_choice']=motor['action']['choice'];sampling['profile_sampled_choice']=selected[0]
 return selected[0],buttons,sampling

def cycle_gate(controls):
 previous='released';cycles=0
 for c in controls:
  current=c['buttons']['jump']
  if previous=='held' and current=='released':cycles+=1
  previous=current
 return cycles>=2

def screen_png(rgb):
 b=io.BytesIO();Image.fromarray(rgb).crop((0,80,256,240)).resize((768,480),Image.Resampling.NEAREST).save(b,format='PNG');return b.getvalue()

def policy_body(model,images,controls,prior_plans,cadence,stage,current_plan=None):
 # No emulator/native-state argument exists in the policy input boundary.
 held_A = controls[-1]['buttons']['jump'] if controls else 'released'
 text=dict(last_chosen_A=held_A,A_edge_semantics='A held through landing does not autojump again. A fresh supported takeoff requires A previously released. Holding A during ongoing ascent preserves height.',instructions=RULES,stage=stage,next_interval_native_frames=cadence,previous_chosen_controls=list(controls)[-3:],past_self_generated_plans=list(prior_plans),evidence='Only the screenshots below reveal the scene. Past plans and current plan are uncertain model hypotheses. CURRENT screenshot first, followed by PAST screenshots from most recent to oldest. Infer motion by comparing past views toward the first current view.')
 if current_plan is not None:text['current_self_generated_plan']=current_plan
 parts=[canonical(text).decode()]
 for i,png in enumerate(reversed(images)):
  parts+=['CURRENT screenshot; the game has not advanced since planning.' if i==0 else 'PAST screenshot for visual motion context; older than the first CURRENT screenshot.',{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(png).decode()}}]
 questions=json.loads(json.dumps(PLAN_QUESTIONS if stage=='plan' else ACTION_QUESTIONS))
 if cycle_gate(controls):
  meta=json.loads(parts[0]);meta['next_interval_native_frames']='Planner chooses exactly 2, 4, 6 or 12 native frames now. The motor then receives that exact selected interval before choosing buttons. No sensor-triggered stopping.' if stage=='plan' else DURATIONS[current_plan['duration']['choice']]
  meta['instructions']+=' Generic completion mechanics: touch the actual flagpole above its solid base. A visible solid base or ascending block step obeys the same side-collision rule as other solids: feet must get above the top before crossing its side. Holding right does not automatically climb a step. Choose any necessary jump yourself from the actual pixels.'
  parts[0]=canonical(meta).decode()
  if stage=='plan':questions['duration']=DURATION_QUESTION
 return dict(model=model.get('request_model',model['id']),provider=model['provider'],state=parts,questions=questions)
