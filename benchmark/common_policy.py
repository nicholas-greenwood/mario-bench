"""Shared model-neutral World 1-1 controllers; no emulator access."""
from __future__ import annotations
from copy import deepcopy
import base64
import io
import math
import random
from PIL import Image
from benchmark.client import canonical
from benchmark.profiles.state_v1 import exposed_surfaces
from prototype.control import ACTIONS
from prototype.decisions import PolicyError

DURATIONS = {'precision_2': 2, 'precision_4': 4, 'routine_6': 6, 'travel_8': 8, 'sustain_12': 12}
RULES = '''Play Super Mario Bros. World 1-1 to touch the flagpole alive. Right advances, left retreats, and B runs faster and makes jumps travel farther. Momentum persists when buttons are released. A starts a jump only on a fresh release-to-press edge while standing on solid support. Holding A during ascent increases height and distance; releasing early makes a low hop. Pressing A while airborne cannot start another jump. Release A during descent to prepare the next grounded takeoff. Keeping A held through landing does not jump again. Pipes, blocks and stairs support Mario on their tops; feet must rise above a solid top before crossing its side. Walking into a solid side does not climb it. Ceilings interrupt ascent. Enemy side contact and falling into gaps are dangerous; descending onto an ordinary walking enemy can stomp it. Approach a visible floor edge before a gap jump; jumping far before the gap can leave the descent above the gap. Preserve enough height and forward travel to land on visible safe support. A small raised landing can require less forward acceleration. Use the current evidence to judge takeoff, ascent, descent and actual support contact. Touch the actual flagpole above its solid base; its base and nearby steps obey ordinary solid-side collision rules. Every controller input is chosen by the model, and is held constant for the declared interval. The game pauses throughout inference.'''
ACTION_QUESTION = dict(type='choice', instructions='Choose the complete controller input that best advances Mario alive over the stated native-frame interval. Evaluate the resulting trajectory and landing. All twelve choices are available.', criteria={name: f'Hold horizontal={v["horizontal"]}, B(run)={v["run"]}, A(jump)={v["jump"]}; vertical released throughout the interval.' for name, v in ACTIONS.items()})
DURATION_QUESTION = dict(type='choice', instructions='Choose how many native frames your next complete controller input should be held before another observation. The following motor decision sees your chosen interval and selects all buttons. Use a short interval when precise contact or input-edge timing matters, and a longer interval when the visible trajectory has room.', criteria={k: f'Hold the next model-chosen complete buttons for {n} native frames, then observe again.' for k,n in DURATIONS.items()})
NEUTRAL = dict(horizontal='released', vertical='released', jump='released', run='released')


def validate(response, body, model):
    if not isinstance(response, dict) or response.get('error'):
        raise PolicyError('Expected a native decision response')
    if response.get('model') != model['expected_returned_model'] or response.get('provider') not in model['expected_returned_provider_names']:
        raise PolicyError('Returned model/provider differs from pinned expected identity')
    answers = response.get('answers')
    if not isinstance(answers, dict) or set(answers) != set(body['questions']):
        raise PolicyError('Response question keys differ from requested contract')
    for name, question in body['questions'].items():
        a = answers[name]
        if not isinstance(a, dict) or a.get('type') != 'choice' or not isinstance(a.get('choice'),str) or a.get('choice') not in question['criteria']:
            raise PolicyError('Invalid native choice')
        p = a.get('probabilities')
        if not isinstance(p, dict) or set(p) != set(question['criteria']):
            raise PolicyError('Native complete probability keys differ from contract')
        if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in p.values()) or abs(sum(p.values())-1) >= .03:
            raise PolicyError('Invalid native probability distribution')
    return dict(model=response['model'], provider=response['provider'], usage=response.get('usage', {}), answers=deepcopy(answers))


def state_observation(state):
    p = state['player']
    phase = 'grounded' if p['grounded'] else 'ascending' if p['vy_px_per_frame'] < 0 else 'descending' if p['vy_px_per_frame'] > 0 else 'airborne apex'
    ready = p['grounded'] and state['buttons']['jump'] == 'released'
    return RULES + f'\nCurrent jump phase: {phase}. Fresh supported takeoff available now={ready}.\n' + exposed_surfaces(state, 4)


def _png(image):
    stream=io.BytesIO(); image.save(stream,format='PNG'); return stream.getvalue()


def _part(png):
    return {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(png).decode()}}


class CommonSession:
    """One model's fixed controller. Image input boundary accepts PNG/clock only."""
    def __init__(self, model, track, *, temperature=None, sampler_seed=None):
        if track not in ('state','image'):
            raise ValueError('Unknown observation track')
        if track == 'image' and (temperature not in (.05,.2) or type(sampler_seed) is not int):
            raise ValueError('Image sampler requires a frozen temperature and integer seed')
        self.model=deepcopy(model);self.track=track;self.temperature=temperature;self.seed=sampler_seed
        self.rng=random.Random(sampler_seed);self.controls=[];self.previous=[];self.frame=None
        self.images=None;self.text=None;self.duration=None

    @property
    def stages(self):
        return ('duration','motor') if self.track=='image' else ('motor',)

    def begin_state(self, state):
        if self.track!='state':
            raise ValueError('Pixels-only controller cannot accept RAM state')
        self.text=state_observation(state);self.frame=state['frame'];self.duration=4

    def begin_image(self, png, *, frame):
        if self.track!='image' or type(frame) is not int or frame<0 or not isinstance(png, bytes):
            raise ValueError('Image boundary requires actual PNG bytes and native clock')
        image=Image.open(io.BytesIO(png));image.load()
        if image.size!=(256,240) or image.mode!='RGB':
            raise ValueError('Expected native 256x240 RGB screenshot')
        self.frame=frame;self.duration=None
        full=_png(image.resize((512,480),Image.Resampling.NEAREST))
        crop=_png(image.crop((0,80,256,240)).resize((768,480),Image.Resampling.NEAREST))
        self.images=(full,crop)

    def body(self, stage):
        if stage not in self.stages or self.frame is None:
            raise ValueError('Invalid controller stage or observation')
        questions={'duration':deepcopy(DURATION_QUESTION)} if stage=='duration' else {'action':deepcopy(ACTION_QUESTION)}
        if self.track=='state':
            evidence={'observation_text':self.text} if self.model.get('state_serialization')=='json_object' else self.text
        else:
            if stage=='motor' and self.duration is None:
                raise ValueError('Motor must receive the native duration choice first')
            meta=dict(game='Super Mario Bros. World 1-1',rules=RULES,stage=stage,native_frame=self.frame,previous_chosen_controls=[dict(c,age_native_frames=self.frame-c['frame_after']) for c in self.controls[-3:]],last_chosen_A=self.controls[-1]['buttons']['jump'] if self.controls else 'released',observation='CURRENT fixed lower gameplay crop first (native x0:256,y80:240 enlarged3x horizontally and vertically); ENTIRE same CURRENT screen second (native256x240 enlarged2x). Mario can leave the crop: use the entire current screen. Both are actual pixels, with nearest-neighbour scaling. Past entire screens follow, most recent first; compare their labelled native ages to infer motion.',next_interval_native_frames=list(DURATIONS.values()) if stage=='duration' else self.duration)
            full,crop=self.images
            evidence=[canonical(meta).decode(),'CURRENT lower gameplay crop.',_part(crop),'ENTIRE same CURRENT screenshot.',_part(full)]
            for f,past in reversed(self.previous[-2:]):
                evidence += [f'PAST ENTIRE screenshot; native frame {f}; age {self.frame-f} native frames.',_part(past)]
        return dict(model=self.model.get('request_model',self.model['id']),provider=deepcopy(self.model['provider']),state=evidence,questions=questions)

    def parse(self,response,body,header_id=None):
        return validate(response,body,self.model)

    def accept_duration(self,response,body):
        parsed=self.parse(response,body)
        self.duration=DURATIONS[parsed['answers']['duration']['choice']]

    def choose(self,response,body):
        parsed=self.parse(response,body);a=parsed['answers']['action'];selected=a['choice'];sampling=None
        if self.track=='image':
            p=a['probabilities'];keys=sorted(p);w={k:p[k]**(1/self.temperature) for k in keys};total=sum(w.values())
            if total<=0:raise PolicyError('Zero tempered probability mass')
            tempered={k:w[k]/total for k in keys};before=self.rng.getstate();draw=self.rng.random();cumulative=0.;selected=keys[-1]
            for k in keys:
                cumulative+=tempered[k]
                if draw<cumulative:selected=k;break
            sampling=dict(native_choice=a['choice'],sampled_choice=selected,temperature=self.temperature,seed=self.seed,raw_probabilities=p,tempered_probabilities=tempered,random_uniform=draw,rng_state_before=before,rng_state_after=self.rng.getstate())
        return dict(buttons=dict(ACTIONS[selected]),choice=selected,requested_frames=self.duration,sampling=sampling)

    def advance(self,*,buttons,frame_after,actual_frames):
        self.controls.append(dict(frame_before=self.frame,frame_after=frame_after,actual_native_frames=actual_frames,buttons=dict(buttons)))
        self.controls=self.controls[-3:]
        if self.track=='image':
            self.previous.append((self.frame,self.images[0]));self.previous=self.previous[-2:]
