"""Frozen current-observation/controller contract used by verified World 1-1 clears.

All controls are model selected. These functions never advance or edit the emulator.
The image track must receive only pixels and declared controller/timing metadata.
"""
from __future__ import annotations

ACTIONS = {'left_walk_release': {'horizontal': 'left', 'vertical': 'released', 'run': 'released', 'jump': 'released'}, 'left_walk_jump': {'horizontal': 'left', 'vertical': 'released', 'run': 'released', 'jump': 'held'}, 'left_run_release': {'horizontal': 'left', 'vertical': 'released', 'run': 'held', 'jump': 'released'}, 'left_run_jump': {'horizontal': 'left', 'vertical': 'released', 'run': 'held', 'jump': 'held'}, 'released_walk_release': {'horizontal': 'released', 'vertical': 'released', 'run': 'released', 'jump': 'released'}, 'released_walk_jump': {'horizontal': 'released', 'vertical': 'released', 'run': 'released', 'jump': 'held'}, 'released_run_release': {'horizontal': 'released', 'vertical': 'released', 'run': 'held', 'jump': 'released'}, 'released_run_jump': {'horizontal': 'released', 'vertical': 'released', 'run': 'held', 'jump': 'held'}, 'right_walk_release': {'horizontal': 'right', 'vertical': 'released', 'run': 'released', 'jump': 'released'}, 'right_walk_jump': {'horizontal': 'right', 'vertical': 'released', 'run': 'released', 'jump': 'held'}, 'right_run_release': {'horizontal': 'right', 'vertical': 'released', 'run': 'held', 'jump': 'released'}, 'right_run_jump': {'horizontal': 'right', 'vertical': 'released', 'run': 'held', 'jump': 'held'}}

QUESTIONS = {'action': {'type': 'choice', 'instructions': 'Select the complete controller input that best advances Mario towards the flag alive. Evaluate the next interval and the resulting jump trajectory. All named buttons are held throughout the interval; choose deliberately when to press or release jump.', 'criteria': {'left_walk_release': 'Hold horizontal=left, B(run)=released, A(jump)=released; vertical released.', 'left_walk_jump': 'Hold horizontal=left, B(run)=released, A(jump)=held; vertical released.', 'left_run_release': 'Hold horizontal=left, B(run)=held, A(jump)=released; vertical released.', 'left_run_jump': 'Hold horizontal=left, B(run)=held, A(jump)=held; vertical released.', 'released_walk_release': 'Hold horizontal=released, B(run)=released, A(jump)=released; vertical released.', 'released_walk_jump': 'Hold horizontal=released, B(run)=released, A(jump)=held; vertical released.', 'released_run_release': 'Hold horizontal=released, B(run)=held, A(jump)=released; vertical released.', 'released_run_jump': 'Hold horizontal=released, B(run)=held, A(jump)=held; vertical released.', 'right_walk_release': 'Hold horizontal=right, B(run)=released, A(jump)=released; vertical released.', 'right_walk_jump': 'Hold horizontal=right, B(run)=released, A(jump)=held; vertical released.', 'right_run_release': 'Hold horizontal=right, B(run)=held, A(jump)=released; vertical released.', 'right_run_jump': 'Hold horizontal=right, B(run)=held, A(jump)=held; vertical released.'}}}

RULES = 'Play Super Mario Bros. World 1-1 to the flag. Coordinates are world pixels, x increases right, y increases down. Scene is current visible information, not a future map. Each action lasts the declared interval with physics paused until your answer. A jump starts only on a fresh A press while grounded; keeping A held through landing will NOT jump again. Release A before the next fresh jump. Holding A during ascent increases height; releasing A shortens the jump. B makes running faster and jumps longer. Momentum persists on release. Mario can jump onto pipes, blocks and stairs and must clear floor gaps. Enemy side contact is dangerous, landing from above stomps ordinary walking enemies. Think ahead about visible hazards and the size of your body. All action choices are your own. Reach the flag alive, avoid waiting indefinitely or running into walls. No action or route recommendation is supplied. General jump phases: hold A while ascending when height or distance is needed; release A while descending to prepare the next fresh jump. Releasing A during ascent shortens the jump, but keeping it held through landing prevents the next jump. On the ground a fresh jump needs the A release-to-press edge. For stairs, the feet must rise above each solid step before crossing its side; landing on a raised step permits another jump. A jump begun too far before a gap can end above the gap; the current visible geometry determines takeoff timing.'

def compact_state(s, interval):
 p=s['player'];x=p['x'];feet=p['y']+32;top=p['y']+(16 if p['status']=='small' else 0)
 cols=s['terrain']['columns']; shapes=[]
 names={84:'ground',81:'brick',82:'brick',97:'stair',18:'pipe',19:'pipe',20:'pipe',21:'pipe',16:'pipe',17:'pipe',192:'question block',193:'question block',196:'used block'}
 for row in range(13):
  for c in cols:
   tile=c['tiles'][row]
   if not tile:continue
   name=names.get(tile,f'tile {tile}')
   if shapes and shapes[-1][1]==c['x'] and shapes[-1][2]==32+row*16 and shapes[-1][4]==name:shapes[-1][1]+=16
   else:shapes.append([c['x'],c['x']+16,32+row*16,48+row*16,name])
 # Merge vertically identical spans. This only changes representation of current visible cells.
 for i in range(len(shapes)-1,-1,-1):
  a=shapes[i]
  for b in shapes[:i]:
   if a[0:2]==b[0:2] and a[2]==b[3] and a[4]==b[4]:b[3]=a[3];shapes.pop(i);break
 text=[f'Frame {s['frame']}. Next input is held for {interval} native frames.',f'Mario is {p["status"]}, world x={x}, body horizontal=[{x},{x+16}], body top y={top}, feet y={feet}.',f'Grounded={p["grounded"]}. Horizontal velocity={p["vx_px_per_frame"]} px/frame, vertical velocity={p["vy_px_per_frame"]} px/frame (negative is up).',f'Currently A(jump) is {s["buttons"]["jump"]}; '+('fresh jump is READY if grounded.' if s['buttons']['jump']=='released' else 'a fresh jump is NOT ready: A must first be released, then pressed again while grounded.'),f'Current horizontal={s["buttons"]["horizontal"]}, B(run)={s["buttons"]["run"]}.',f'Visible world x=[{cols[0]["x"]},{cols[-1]["x"]+16}]. Geometry outside this range is unknown.', 'Current visible terrain; dx is measured from Mario left edge; y is world screen-height pixels:']
 for left,right,t,b,kind in shapes:
  text.append(f'{kind}: world x=[{left},{right}], relative dx=[{left-x},{right-x}], top y={t} ({feet-t} px above Mario feet), bottom y={b}.')
 gaps=[]
 for c in cols:
  if c['tiles'][11]==0:
   if gaps and gaps[-1][1]==c['x']:gaps[-1][1]+=16
   else:gaps.append([c['x'],c['x']+16])
 text.append('Floor gaps at y208: '+('; '.join(f'world x[{a},{b}], dx[{a-x},{b-x}], width {b-a}' for a,b in gaps) or 'none in visible area.'))
 text.append('Visible moving objects:')
 for o in s['nearby_objects']:
  ot=o['y']+(8 if o['kind']=='goomba' else 0);ob=o['y']+24
  text.append(f'{o["kind"]}: world x[{o["x"]},{o["x"]+16}], dx[{o["x"]-x},{o["x"]+16-x}], body y[{ot},{ob}], horizontal velocity {o["vx_px_per_frame"]}, state={o["state_raw"]}.')
 if not s['nearby_objects']:text.append('None.')
 text.append('Recent actual positions: '+ '; '.join(f'frame{h["frame"]} x{h["x"]} feet{h["y"]+32} A{h["buttons"]["jump"]}' for h in s['history'][-4:]))
 return '\n'.join(text)

def state_text(state, interval):
    level = state.get("level", "1-1")
    rules = RULES if level == "1-1" else RULES.replace("World 1-1", f"World {level}", 1)
    return rules + "\n" + compact_state(state, interval)


def decode_action_response(result):
    """Validate the native joint choice, then expand that exact choice to buttons."""
    import math
    answer = result.get("answers", {}).get("action", {})
    if not isinstance(answer, dict):
        raise ValueError("Missing joint controller answer")
    choice = answer.get("choice")
    probabilities = answer.get("probabilities")
    if answer.get("type") != "choice" or choice not in ACTIONS:
        raise ValueError("Missing or unsupported joint controller choice")
    if not isinstance(probabilities, dict) or set(probabilities) != set(ACTIONS):
        raise ValueError("Missing full joint action probability distribution")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values()):
        raise ValueError("Invalid joint action probabilities")
    if not math.isclose(sum(probabilities.values()), 1, abs_tol=.03):
        raise ValueError("Joint action probabilities do not sum to one")
    return dict(ACTIONS[choice]), {"action": probabilities}
