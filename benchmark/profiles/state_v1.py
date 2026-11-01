"""Frozen visible-state formatters for the published development checkpoint."""
from __future__ import annotations

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

def compact_phase(state, interval):
    p = state['player']
    phase = 'GROUNDED' if p['grounded'] else ('ASCENDING' if p['vy_px_per_frame'] < 0 else 'DESCENDING' if p['vy_px_per_frame'] > 0 else 'AIRBORNE APEX')
    lines = compact_state(state, interval).splitlines()
    lines[3] = f'A(jump) is {state["buttons"]["jump"]}. Fresh grounded takeoff available now={p["grounded"] and state["buttons"]["jump"] == "released"}.'
    return f'Current jump phase: {phase}.\n' + '\n'.join(lines)

def exposed_surfaces(state, interval):
 s=state;p=s['player'];x=p['x'];feet=p['y']+32;cols=s['terrain']['columns'];solid={16,17,18,19,20,21,81,82,84,87,88,97,192,193,196};tops=[]
 for c in cols:
  for row,tile in enumerate(c['tiles']):
   if tile in solid and (row==0 or c['tiles'][row-1] not in solid):
    y=32+row*16
    if tops and tops[-1][1]==c['x'] and tops[-1][2]==y:tops[-1][1]+=16
    else:tops.append([c['x'],c['x']+16,y])
 tops.sort()
 text=['CURRENT EXPOSED TOP SURFACES (not predictions): on descent Mario may land when his feet cross a surface top while his body overlaps its x span. Walking into a solid side below its top does not climb it.']
 for a,b,y in tops:
  if b>=x-32:text.append(f'Standable top: world x[{a},{b}], relative dx[{a-x},{b-x}], top y{y}; {feet-y}px above current feet; width{b-a}.')
 return '\n'.join(text)+'\n'+compact_state(state,interval)
