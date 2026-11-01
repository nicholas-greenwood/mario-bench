"""No-network checks for lossless documented state-envelope adapters."""
import argparse
import json
from pathlib import Path
from benchmark.client import request_body, FakeClient
from benchmark.run import snapshot, png
from prototype.emulator import MarioGame


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--frozen-request',type=Path);parser.add_argument('--native-state',type=Path);args=parser.parse_args()
 model=next(m for m in json.loads(Path('benchmark/models.json').read_text())['models'] if m['id']=='openai/gpt-6-luna-decisions')
 game=MarioGame()
 try:
  state=snapshot(game,4);text=request_body(model,state,state_serialization="text");wrapped=request_body(model,state,state_serialization='json_object')
  assert wrapped['state']=={'observation_text':text['state']}
  configured=dict(model,state_serialization='json_object')
  assert request_body(configured,state)['state']==wrapped['state']
  assert request_body(configured,state,state_serialization='text')['state']==text['state']
  assert {k:v for k,v in wrapped.items() if k!='state'}=={k:v for k,v in text.items() if k!='state'}
  assert json.loads(json.dumps(wrapped))['state']['observation_text']==text['state']
  assert FakeClient().call(wrapped)['valid']
  visual=request_body(configured,state,png(game));assert isinstance(visual['state'],list)
  for kind in ('json_object','invalid'):
   try:request_body(model,state,png(game),state_serialization=kind)
   except ValueError:pass
   else:raise AssertionError('Pixels input must reject state adapters')
  if args.frozen_request:
   assert args.native_state, '--native-state is required with --frozen-request'
   original=json.loads(args.frozen_request.read_text())['body'];before=json.loads(args.native_state.read_text())
   assert request_body(model,before,state_serialization="text")==original
   changed=request_body(model,before,state_serialization='json_object');assert changed['state']['observation_text']==original['state'];assert all(changed[k]==original[k] for k in original if k!='state')
  assert game.frame==0
 finally:game.close()
 print('PASS: exact evidence bytes/questions/pin, explicit JSON wire shape, frozen-failure fixture, unchanged default text/pixels, no model requests')
if __name__=='__main__':main()
