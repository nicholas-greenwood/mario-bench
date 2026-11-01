"""Image-only fixed7 session. No emulator/RAM observation entry point."""
from collections import deque
from copy import deepcopy
import random
from benchmark import common_image_v2_policy as policy
from benchmark.profiles.image_v1 import PROFILES
from prototype.decisions import PolicyError

ACTIONS=PROFILES[policy.BUILDER_PROFILE_ID]['questions']['action']['criteria']
NEUTRAL=dict(horizontal='released',vertical='released',jump='released',run='released')

class CommonImageSession:
    def __init__(self,model,track='image',*,temperature=None,sampler_seed=None):
        if track!='image' or temperature not in policy.TEMPERATURES or type(sampler_seed) is not int:
            raise ValueError('Image v2 requires an image track, preregistered temperature and integer local seed')
        self.model=deepcopy(model);self.track=track;self.temperature=temperature;self.seed=sampler_seed
        self.rng=random.Random(sampler_seed);self.controls=deque(maxlen=2);self.previous=deque(maxlen=1)
        self.frame=None;self.index=0;self.current=None;self.buttons=dict(NEUTRAL);self.duration=7
    @property
    def stages(self):return ('motor',)
    def begin_image(self,png,*,frame):
        if self.current is not None:raise ValueError('Current image has not been advanced')
        if type(frame) is not int or frame<0:raise ValueError('Invalid declared native frame')
        if self.controls and self.controls[-1]['frame']+self.controls[-1]['frames']!=frame:
            raise ValueError('Image native clock differs from actual own controller history')
        self.current=png;self.frame=frame
    def body(self,stage):
        if stage!='motor' or self.current is None:raise ValueError('A current full image and single motor stage are required')
        return policy.build_request(self.model,self.current,self.frame,self.index,self.buttons,list(self.controls),list(self.previous))
    def parse(self,raw,body,header_id=None):
        try:parsed=policy.parse(raw,body,self.model)
        except (ValueError,TypeError,KeyError) as error:raise PolicyError(str(error)) from None
        return dict(parsed,model=raw['model'],provider=raw['provider'],usage=deepcopy(raw.get('usage',{})),request_id=raw.get('id') or header_id)
    def choose(self,raw,body):
        # The only RNG operation: called exactly once for an actual committed action.
        return policy.choose(raw,body,self.temperature,self.rng,model=self.model)
    def advance(self,*,buttons,frame_after,actual_frames):
        if self.current is None or type(actual_frames) is not int or not 1<=actual_frames<=7 or frame_after!=self.frame+actual_frames:
            raise ValueError('Actual control advancement differs from the declared fixed7 interval')
        self.controls.append(dict(frame=self.frame,frames=actual_frames,buttons=dict(buttons)))
        self.previous.append((self.frame,self.current));self.buttons=dict(buttons)
        self.frame=frame_after;self.current=None;self.index+=1
