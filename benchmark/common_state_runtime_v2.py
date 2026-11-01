"""Shared compact-state v2 session, with no image policy or per-model controls."""
from copy import deepcopy
from benchmark.common_policy import CommonSession as BaseSession,ACTIONS
from benchmark.common_state_compact_v2 import PROFILE,state_text

class StateCompactSession(BaseSession):
    def __init__(self,model,track,*,temperature=None,sampler_seed=None):
        if track!='state' or temperature is not None or sampler_seed is not None:
            raise ValueError('State v2 uses native choices and fixed4 for all models')
        super().__init__(model,track,temperature=None,sampler_seed=None)
    def begin_state(self,state):
        self.text=state_text(state);self.frame=state['frame'];self.duration=4
    def body(self,stage):
        if stage!='motor' or self.frame is None:raise ValueError('State v2 requires a current state and native motor stage')
        evidence={'observation_text':self.text} if self.model.get('state_serialization')=='json_object' else self.text
        return dict(model=self.model.get('request_model',self.model['id']),provider=deepcopy(self.model['provider']),state=evidence,questions=deepcopy(PROFILE['questions']))
