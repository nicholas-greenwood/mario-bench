"""Frozen pixels-only development input/controller checkpoints; no emulator or API access."""
from __future__ import annotations
import base64, copy, io, json
from PIL import Image

PROFILES = {'pixels-edge-pplx-c7-v1': {'model': 'perplexity/pplx-decider-v1.2-20261016',
                            'provider': {'allow_fallbacks': False, 'only': ['perplexity']},
                            'questions': {'action': {'criteria': {'left_B_held_A_held': 'Horizontal left; B held; A '
                                                                                        'held; vertical released.',
                                                                  'left_B_held_A_released': 'Horizontal left; B held; '
                                                                                            'A released; vertical '
                                                                                            'released.',
                                                                  'left_B_released_A_held': 'Horizontal left; B '
                                                                                            'released; A held; '
                                                                                            'vertical released.',
                                                                  'left_B_released_A_released': 'Horizontal left; B '
                                                                                                'released; A released; '
                                                                                                'vertical released.',
                                                                  'released_B_held_A_held': 'Horizontal released; B '
                                                                                            'held; A held; vertical '
                                                                                            'released.',
                                                                  'released_B_held_A_released': 'Horizontal released; '
                                                                                                'B held; A released; '
                                                                                                'vertical released.',
                                                                  'released_B_released_A_held': 'Horizontal released; '
                                                                                                'B released; A held; '
                                                                                                'vertical released.',
                                                                  'released_B_released_A_released': 'Horizontal '
                                                                                                    'released; B '
                                                                                                    'released; A '
                                                                                                    'released; '
                                                                                                    'vertical '
                                                                                                    'released.',
                                                                  'right_B_held_A_held': 'Horizontal right; B held; A '
                                                                                         'held; vertical released.',
                                                                  'right_B_held_A_released': 'Horizontal right; B '
                                                                                             'held; A released; '
                                                                                             'vertical released.',
                                                                  'right_B_released_A_held': 'Horizontal right; B '
                                                                                             'released; A held; '
                                                                                             'vertical released.',
                                                                  'right_B_released_A_released': 'Horizontal right; B '
                                                                                                 'released; A '
                                                                                                 'released; vertical '
                                                                                                 'released.'},
                                                     'instructions': 'Choose one complete simultaneous BUTTON STATE '
                                                                     'for the interval, not an abstract jump request. '
                                                                     'If A is already held, choosing A_held continues '
                                                                     'that same press and cannot start a fresh jump '
                                                                     'after landing. Holding A remains useful during '
                                                                     'ascent. Infer surfaces and motion from the '
                                                                     'current/past images.',
                                                     'type': 'choice'}},
                            'cadence_frames': 7,
                            'metadata_template': {'a_button_note': 'A is currently RELEASED. Selecting A_held creates '
                                                                   'a fresh press, which can start a jump only if '
                                                                   'Mario is on a surface.',
                                                  'control_interval_frames': 7,
                                                  'currently_held_buttons': {'horizontal': 'released',
                                                                             'jump': 'released',
                                                                             'run': 'released',
                                                                             'vertical': 'released'},
                                                  'game': 'Super Mario Bros., world 1-1',
                                                  'native_frame': 0,
                                                  'observation_interface': 'image_only',
                                                  'previous_model_controls': [],
                                                  'rules_and_button_semantics': 'Play Super Mario Bros 1-1 alive to '
                                                                                'the flag toward the right. Use the '
                                                                                'actual screenshots to infer Mario, '
                                                                                'enemies, surfaces and motion. Game '
                                                                                'physics pauses while you decide. The '
                                                                                'selected complete button state is '
                                                                                'held for the whole declared interval. '
                                                                                'A starts a jump only on a NEW press '
                                                                                'while on a surface. Holding A during '
                                                                                'ascent increases height and airtime; '
                                                                                'releasing during ascent makes a '
                                                                                'shorter jump. Once descending, '
                                                                                'release A to prepare the next fresh '
                                                                                'press. Holding A through landing '
                                                                                'cannot start another jump. B runs '
                                                                                'faster and farther; momentum persists '
                                                                                'on release. Jump onto solid '
                                                                                'pipes/blocks/stairs or over gaps; '
                                                                                'time takeoff from the visible ground. '
                                                                                'Enemies hurt on side contact and can '
                                                                                'be stomped from above. Background '
                                                                                'hills/clouds are decorative. You '
                                                                                'choose all controls; no automatic '
                                                                                'correction exists.',
                                                  'screenshot_format': 'CURRENT fullpaused screenshot FIRST; remaining '
                                                                       'images are PAST motion context, '
                                                                       'oldest-to-newest. All screens are '
                                                                       'native256x240 enlarged2x nearest.'},
                            'text_suffix': '',
                            'metadata_encoding': 'compact_sorted_json',
                            'controller_interface': 'explicit_joint_A_B_states',
                            'previous_controls_schema': ['frame', 'frames', 'buttons'],
                            'previous_controls_limit': 2,
                            'maximum_previous_full_screens': 1,
                            'image_order': 'current_first_then_past',
                            'image_label_clock': 'native_frame',
                            'current_image_label': 'CURRENT paused screenshot, native frame {clock}.',
                            'past_image_label': 'PAST screenshot for motion context, native frame {clock}.',
                            'full_image_size': [512, 480],
                            'native_image_size': [256, 240],
                            'interpolation': 'nearest',
                            'normalise_png': True,
                            'crop': None,
                            'a_button_notes': {'released': 'A is currently RELEASED. Selecting A_held creates a fresh '
                                                           'press, which can start a jump only if Mario is on a '
                                                           'surface.',
                                               'held': 'A is ALREADY HELD. Selecting A_held continues this SAME press; '
                                                       'it cannot start a new jump after landing. Holding remains '
                                                       'useful during ascent. Release A to enable a subsequent fresh '
                                                       'press.'},
                            'a_state_duration_source': None},
 'pixels-edge-crop-luna-c7-v1': {'model': 'openai/gpt-6-luna-decisions-20261006',
                                 'provider': {'allow_fallbacks': False, 'only': ['openai']},
                                 'questions': {'action': {'criteria': {'left_B_held_A_held': 'Horizontal left; B held; '
                                                                                             'A held; vertical '
                                                                                             'released.',
                                                                       'left_B_held_A_released': 'Horizontal left; B '
                                                                                                 'held; A released; '
                                                                                                 'vertical released.',
                                                                       'left_B_released_A_held': 'Horizontal left; B '
                                                                                                 'released; A held; '
                                                                                                 'vertical released.',
                                                                       'left_B_released_A_released': 'Horizontal left; '
                                                                                                     'B released; A '
                                                                                                     'released; '
                                                                                                     'vertical '
                                                                                                     'released.',
                                                                       'released_B_held_A_held': 'Horizontal released; '
                                                                                                 'B held; A held; '
                                                                                                 'vertical released.',
                                                                       'released_B_held_A_released': 'Horizontal '
                                                                                                     'released; B '
                                                                                                     'held; A '
                                                                                                     'released; '
                                                                                                     'vertical '
                                                                                                     'released.',
                                                                       'released_B_released_A_held': 'Horizontal '
                                                                                                     'released; B '
                                                                                                     'released; A '
                                                                                                     'held; vertical '
                                                                                                     'released.',
                                                                       'released_B_released_A_released': 'Horizontal '
                                                                                                         'released; B '
                                                                                                         'released; A '
                                                                                                         'released; '
                                                                                                         'vertical '
                                                                                                         'released.',
                                                                       'right_B_held_A_held': 'Horizontal right; B '
                                                                                              'held; A held; vertical '
                                                                                              'released.',
                                                                       'right_B_held_A_released': 'Horizontal right; B '
                                                                                                  'held; A released; '
                                                                                                  'vertical released.',
                                                                       'right_B_released_A_held': 'Horizontal right; B '
                                                                                                  'released; A held; '
                                                                                                  'vertical released.',
                                                                       'right_B_released_A_released': 'Horizontal '
                                                                                                      'right; B '
                                                                                                      'released; A '
                                                                                                      'released; '
                                                                                                      'vertical '
                                                                                                      'released.'},
                                                          'instructions': 'Choose one complete simultaneous BUTTON '
                                                                          'STATE for the interval, not an abstract '
                                                                          'jump request. If A is already held, '
                                                                          'choosing A_held continues that same press '
                                                                          'and cannot start a fresh jump after '
                                                                          'landing. Holding A remains useful during '
                                                                          'ascent. Infer surfaces and motion from the '
                                                                          'current/past images.',
                                                          'type': 'choice'}},
                                 'cadence_frames': 7,
                                 'metadata_template': {'a_button_note': 'A is currently RELEASED. Selecting A_held '
                                                                        'creates a fresh press, which can start a jump '
                                                                        'only if Mario is on a surface.',
                                                       'control_interval_frames': 7,
                                                       'currently_held_buttons': {'horizontal': 'released',
                                                                                  'jump': 'released',
                                                                                  'run': 'released',
                                                                                  'vertical': 'released'},
                                                       'game': 'Super Mario Bros., world 1-1',
                                                       'native_frame': 0,
                                                       'observation_interface': 'image_only',
                                                       'previous_model_controls': [],
                                                       'rules_and_button_semantics': 'Play Super Mario Bros 1-1 alive '
                                                                                     'to the flag toward the right. '
                                                                                     'Use the actual screenshots to '
                                                                                     'infer Mario, enemies, surfaces '
                                                                                     'and motion. Game physics pauses '
                                                                                     'while you decide. The selected '
                                                                                     'complete button state is held '
                                                                                     'for the whole declared interval. '
                                                                                     'A starts a jump only on a NEW '
                                                                                     'press while on a surface. '
                                                                                     'Holding A during ascent '
                                                                                     'increases height and airtime; '
                                                                                     'releasing during ascent makes a '
                                                                                     'shorter jump. Once descending, '
                                                                                     'release A to prepare the next '
                                                                                     'fresh press. Holding A through '
                                                                                     'landing cannot start another '
                                                                                     'jump. B runs faster and farther; '
                                                                                     'momentum persists on release. '
                                                                                     'Jump onto solid '
                                                                                     'pipes/blocks/stairs or over '
                                                                                     'gaps; time takeoff from the '
                                                                                     'visible ground. Enemies hurt on '
                                                                                     'side contact and can be stomped '
                                                                                     'from above. Background '
                                                                                     'hills/clouds are decorative. You '
                                                                                     'choose all controls; no '
                                                                                     'automatic correction exists.',
                                                       'screenshot_format': 'CURRENT fullpaused screenshot FIRST; '
                                                                            'remaining images are PAST motion context, '
                                                                            'oldest-to-newest. All screens are '
                                                                            'native256x240 enlarged2x nearest.'},
                                 'text_suffix': '',
                                 'metadata_encoding': 'compact_sorted_json',
                                 'controller_interface': 'explicit_joint_A_B_states',
                                 'previous_controls_schema': ['frame', 'frames', 'buttons'],
                                 'previous_controls_limit': 2,
                                 'maximum_previous_full_screens': 1,
                                 'image_order': 'current_first_then_past',
                                 'image_label_clock': 'native_frame',
                                 'current_image_label': 'CURRENT paused screenshot, native frame {clock}.',
                                 'past_image_label': 'PAST screenshot for motion context, native frame {clock}.',
                                 'full_image_size': [512, 480],
                                 'native_image_size': [256, 240],
                                 'interpolation': 'nearest',
                                 'normalise_png': True,
                                 'crop': {'native_box': [0, 80, 256, 240],
                                          'size': [768, 480],
                                          'label': 'Static visual game rules: Mario is the red/orange humanoid. Brown '
                                                   'mushroom faces and green turtles are dangerous walking enemies. '
                                                   'Brick-pattern ground, blocks and green pipes are solid; background '
                                                   'hills and clouds are decorative. The following image is a fixed '
                                                   'crop of the bottom two thirds of the same CURRENT paused '
                                                   'screenshot, enlarged3x nearest-neighbour for sprite detail; it '
                                                   'contains only actual pixels, no annotations.'},
                                 'a_button_notes': {'released': 'A is currently RELEASED. Selecting A_held creates a '
                                                                'fresh press, which can start a jump only if Mario is '
                                                                'on a surface.',
                                                    'held': 'A is ALREADY HELD. Selecting A_held continues this SAME '
                                                            'press; it cannot start a new jump after landing. Holding '
                                                            'remains useful during ascent. Release A to enable a '
                                                            'subsequent fresh press.'},
                                 'a_state_duration_source': None},
 'pixels-edge-a-age-pplx-c4-v1': {'model': 'perplexity/pplx-decider-v1.2-20261016',
                                  'provider': {'allow_fallbacks': False, 'only': ['perplexity']},
                                  'questions': {'action': {'criteria': {'left_B_held_A_held': 'Horizontal left; B '
                                                                                              'held; A held; vertical '
                                                                                              'released.',
                                                                        'left_B_held_A_released': 'Horizontal left; B '
                                                                                                  'held; A released; '
                                                                                                  'vertical released.',
                                                                        'left_B_released_A_held': 'Horizontal left; B '
                                                                                                  'released; A held; '
                                                                                                  'vertical released.',
                                                                        'left_B_released_A_released': 'Horizontal '
                                                                                                      'left; B '
                                                                                                      'released; A '
                                                                                                      'released; '
                                                                                                      'vertical '
                                                                                                      'released.',
                                                                        'released_B_held_A_held': 'Horizontal '
                                                                                                  'released; B held; A '
                                                                                                  'held; vertical '
                                                                                                  'released.',
                                                                        'released_B_held_A_released': 'Horizontal '
                                                                                                      'released; B '
                                                                                                      'held; A '
                                                                                                      'released; '
                                                                                                      'vertical '
                                                                                                      'released.',
                                                                        'released_B_released_A_held': 'Horizontal '
                                                                                                      'released; B '
                                                                                                      'released; A '
                                                                                                      'held; vertical '
                                                                                                      'released.',
                                                                        'released_B_released_A_released': 'Horizontal '
                                                                                                          'released; B '
                                                                                                          'released; A '
                                                                                                          'released; '
                                                                                                          'vertical '
                                                                                                          'released.',
                                                                        'right_B_held_A_held': 'Horizontal right; B '
                                                                                               'held; A held; vertical '
                                                                                               'released.',
                                                                        'right_B_held_A_released': 'Horizontal right; '
                                                                                                   'B held; A '
                                                                                                   'released; vertical '
                                                                                                   'released.',
                                                                        'right_B_released_A_held': 'Horizontal right; '
                                                                                                   'B released; A '
                                                                                                   'held; vertical '
                                                                                                   'released.',
                                                                        'right_B_released_A_released': 'Horizontal '
                                                                                                       'right; B '
                                                                                                       'released; A '
                                                                                                       'released; '
                                                                                                       'vertical '
                                                                                                       'released.'},
                                                           'instructions': 'Choose one complete simultaneous BUTTON '
                                                                           'STATE for the interval, not an abstract '
                                                                           'jump request. If A is already held, '
                                                                           'choosing A_held continues that same press '
                                                                           'and cannot start a fresh jump after '
                                                                           'landing. Holding A remains useful during '
                                                                           'ascent. Infer surfaces and motion from the '
                                                                           'current/past images.',
                                                           'type': 'choice'}},
                                  'cadence_frames': 4,
                                  'metadata_template': {'a_button_note': 'A is currently RELEASED. Selecting A_held '
                                                                         'creates a fresh press, which can start a '
                                                                         'jump only if Mario is on a surface. This '
                                                                         'same A state has continued for 0 '
                                                                         'nativeframes since its last change, counted '
                                                                         'only from your prior controller choices.',
                                                        'a_button_state_duration_frames': 0,
                                                        'control_interval_frames': 4,
                                                        'currently_held_buttons': {'horizontal': 'released',
                                                                                   'jump': 'released',
                                                                                   'run': 'released',
                                                                                   'vertical': 'released'},
                                                        'game': 'Super Mario Bros., world 1-1',
                                                        'native_frame': 0,
                                                        'observation_interface': 'image_only',
                                                        'previous_model_controls': [],
                                                        'rules_and_button_semantics': 'Play Super Mario Bros 1-1 alive '
                                                                                      'to the flag toward the right. '
                                                                                      'Use the actual screenshots to '
                                                                                      'infer Mario, enemies, surfaces '
                                                                                      'and motion. Game physics pauses '
                                                                                      'while you decide. The selected '
                                                                                      'complete button state is held '
                                                                                      'for the whole declared '
                                                                                      'interval. A starts a jump only '
                                                                                      'on a NEW press while on a '
                                                                                      'surface. Holding A during '
                                                                                      'ascent increases height and '
                                                                                      'airtime; releasing during '
                                                                                      'ascent makes a shorter jump. '
                                                                                      'Once descending, release A to '
                                                                                      'prepare the next fresh press. '
                                                                                      'Holding A through landing '
                                                                                      'cannot start another jump. B '
                                                                                      'runs faster and farther; '
                                                                                      'momentum persists on release. '
                                                                                      'Jump onto solid '
                                                                                      'pipes/blocks/stairs or over '
                                                                                      'gaps; time takeoff from the '
                                                                                      'visible ground. Enemies hurt on '
                                                                                      'side contact and can be stomped '
                                                                                      'from above. Background '
                                                                                      'hills/clouds are decorative. '
                                                                                      'You choose all controls; no '
                                                                                      'automatic correction exists.',
                                                        'screenshot_format': 'CURRENT fullpaused screenshot FIRST; '
                                                                             'remaining images are PAST motion '
                                                                             'context, oldest-to-newest. All screens '
                                                                             'are native256x240 enlarged2x nearest.'},
                                  'text_suffix': '',
                                  'metadata_encoding': 'compact_sorted_json',
                                  'controller_interface': 'explicit_joint_A_B_states',
                                  'previous_controls_schema': ['frame', 'frames', 'buttons'],
                                  'previous_controls_limit': 2,
                                  'maximum_previous_full_screens': 1,
                                  'image_order': 'current_first_then_past',
                                  'image_label_clock': 'native_frame',
                                  'current_image_label': 'CURRENT paused screenshot, native frame {clock}.',
                                  'past_image_label': 'PAST screenshot for motion context, native frame {clock}.',
                                  'full_image_size': [512, 480],
                                  'native_image_size': [256, 240],
                                  'interpolation': 'nearest',
                                  'normalise_png': True,
                                  'crop': None,
                                  'a_button_notes': {'released': 'A is currently RELEASED. Selecting A_held creates a '
                                                                 'fresh press, which can start a jump only if Mario is '
                                                                 'on a surface.',
                                                     'held': 'A is ALREADY HELD. Selecting A_held continues this SAME '
                                                             'press; it cannot start a new jump after landing. Holding '
                                                             'remains useful during ascent. Release A to enable a '
                                                             'subsequent fresh press.'},
                                  'a_state_duration_source': 'sum of prior model-chosen held/released native-frame '
                                                             'durations; no emulator sensor'},
 'pixels-four-question-jev-c6-v1': {'model': 'typesafe/jev-1.14-20261014',
                                    'provider': {'allow_fallbacks': False, 'only': ['typesafe']},
                                    'questions': {'horizontal': {'criteria': {'left': 'Hold left.',
                                                                              'released': 'Release horizontal '
                                                                                          'movement.',
                                                                              'right': 'Hold right.'},
                                                                 'instructions': 'Choose horizontal movement for '
                                                                                 'survival and progress toward the '
                                                                                 'flag based on the images.',
                                                                 'type': 'choice'},
                                                  'jump': {'criteria': {'held': 'Press/hold A: initiate jump if on a '
                                                                                'surface and eligible, or sustain '
                                                                                'existing jump.',
                                                                        'released': 'Release A: shorten/finish jump '
                                                                                    'and allow a fresh press for the '
                                                                                    'next jump.'},
                                                           'instructions': 'Choose A from the screenshots and '
                                                                           'current/previous button state. A held '
                                                                           'sustains ascent and airtime; A released '
                                                                           'early makes a short hop. For a new jump, '
                                                                           'release A before pressing. Decide whether '
                                                                           'starting, sustaining, or finishing a jump '
                                                                           'best clears the visible hazard.',
                                                           'type': 'choice'},
                                                  'run': {'criteria': {'held': 'Hold B to run faster/fire when '
                                                                               'eligible.',
                                                                       'released': 'Release B to walk at ordinary '
                                                                                   'speed.'},
                                                          'instructions': 'Choose B. Running moves faster and farther; '
                                                                          'walking offers more precise control.',
                                                          'type': 'choice'},
                                                  'vertical': {'criteria': {'down': 'Hold down, crouching or entering '
                                                                                    'a pipe when eligible.',
                                                                            'released': 'Release vertical directions.',
                                                                            'up': 'Hold up.'},
                                                               'instructions': 'Choose vertical control. Usually '
                                                                               'released in ordinary movement; up/down '
                                                                               'do not jump.',
                                                               'type': 'choice'}},
                                    'cadence_frames': 6,
                                    'metadata_template': {'game': 'Super Mario Bros 1-1',
                                                          'instructions': 'Play Super Mario Bros world 1-1 to reach '
                                                                          'the flag alive by moving right. All '
                                                                          'evidence about the game comes from the '
                                                                          'screenshots; infer Mario, enemies, '
                                                                          'surfaces, and motion visually. The game is '
                                                                          'paused while you decide. You choose all '
                                                                          'four simultaneous button states, held for '
                                                                          'the stated number of native 60Hz frames. '
                                                                          'Right/left moves, A jumps, B runs, down '
                                                                          'crouches or enters pipes. Holding A '
                                                                          'sustains a jump; release A before a fresh '
                                                                          'jump after landing. Holding A through '
                                                                          'landing does not start another jump. Side '
                                                                          'contact with enemies and falling into gaps '
                                                                          'are dangerous; landing on an enemy can '
                                                                          'defeat it. Aim jumps using visible '
                                                                          'obstacles and motion, and release A when '
                                                                          'appropriate to prepare another jump. Images '
                                                                          'are native 256x240, nearest-neighbour '
                                                                          'enlarged to 512x480; chronological oldest '
                                                                          'first, current last. No automatic action '
                                                                          'correction or controller assists exist.',
                                                          'next_control_interval_native_frames': 6,
                                                          'previous_controls': []},
                                    'text_suffix': ' General control guidance: walk for precision near hazards; '
                                                   'high-speed movement requires anticipating collisions. Jumping '
                                                   'underneath a solid block can stop the ascent. Sustained A '
                                                   'increases height; releasing A very early can make a jump too short '
                                                   'to clear tall obstacles. A pressed while airborne cannot restart a '
                                                   'jump. If repeated jumps cannot clear an obstacle, consider backing '
                                                   'away to gain running momentum. Work out the actual situation from '
                                                   'the screenshots. Watch where the solid ground ends: initiate gap '
                                                   'jumps while still standing on the ground, before moving beyond the '
                                                   'edge. Do not confuse decorative background hills with solid '
                                                   'platforms. When approaching an enemy beneath low blocks, account '
                                                   'for the ceiling interrupting a jump. General gap-jumping '
                                                   'principle: approach toward the visible edge before beginning a gap '
                                                   'jump; jumping far before a gap can leave you descending into it. '
                                                   'Sustain A during ascent for enough height and airtime to clear the '
                                                   'gap or tall obstacle. Let the image determine whether you have '
                                                   'actually cleared it. Releasing A very shortly after takeoff makes '
                                                   'a low short hop.',
                                    'metadata_encoding': 'compact_sorted_json',
                                    'controller_interface': 'four_independent_simultaneous_button_states',
                                    'previous_controls_schema': ['decision', 'buttons', 'held_native_frames'],
                                    'previous_controls_limit': 12,
                                    'maximum_previous_full_screens': 1,
                                    'image_order': 'past_then_current',
                                    'image_label_clock': 'decision_index',
                                    'current_image_label': 'Screenshot taken before decision {clock}',
                                    'past_image_label': 'Screenshot taken before decision {clock}',
                                    'full_image_size': [512, 480],
                                    'native_image_size': [256, 240],
                                    'interpolation': 'nearest',
                                    'normalise_png': False,
                                    'crop': None,
                                    'a_button_notes': {},
                                    'a_state_duration_source': None}}

def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

def _buttons(value):
    allowed={'horizontal':{'left','released','right'},'vertical':{'up','released','down'},'jump':{'held','released'},'run':{'held','released'}}
    if set(value)!=set(allowed) or any(value[k] not in v for k,v in allowed.items()):
        raise ValueError('Exactly four valid declared button states are required')
    return dict(value)

def advance_a_state(previous_state,previous_duration,buttons,native_frames):
    """Update memory solely from a committed model-chosen input interval."""
    state=_buttons(buttons)['jump']
    return state,previous_duration+native_frames if state==previous_state else native_frames

def _png(data,normalise):
    if not isinstance(data,bytes) or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Actual screenshot PNG bytes required')
    image=Image.open(io.BytesIO(data)).convert('RGB')
    if image.size==(256,240):image=image.resize((512,480),Image.Resampling.NEAREST);normalise=True
    if image.size!=(512,480):raise ValueError('Full screenshots must be 512x480 nearest enlargements of native256x240')
    native=image.resize((256,240),Image.Resampling.NEAREST)
    if native.resize((512,480),Image.Resampling.NEAREST).tobytes()!=image.tobytes():raise ValueError('Screenshot is not exact nearest-neighbour pixels')
    if normalise:
        stream=io.BytesIO();image.save(stream,format='PNG');data=stream.getvalue()
    return data

def profile_request(profile_id,*,image_png,frame,decision_index,buttons,previous_controls=(),previous_images=(),a_state_frames=0):
    """Build a frozen native Decisions request from images and declared controls only.

    previous_images are (native_frame_or_decision_index,PNG) pairs. Previous controls
    use the exact whitelisted schema declared in the profile. No game object or
    structured emulator observation can be passed to this function.
    """
    p=PROFILES[profile_id];meta=copy.deepcopy(p['metadata_template']);current=_buttons(buttons);records=[]
    for record in previous_controls:
        if set(record)!=set(p['previous_controls_schema']):raise ValueError('RAM or unknown control-history fields forbidden')
        _buttons(record['buttons']);records.append(copy.deepcopy(record))
    records=records[-p['previous_controls_limit']:]
    if 'observation_interface' in meta:
        meta['native_frame']=frame;meta['control_interval_frames']=p['cadence_frames'];meta['currently_held_buttons']=current;meta['previous_model_controls']=records
        if p['a_button_notes']:
            meta['a_button_note']=p['a_button_notes'][current['jump']]
            if p['a_state_duration_source']:
                meta['a_button_state_duration_frames']=a_state_frames
                meta['a_button_note']+=' This same A state has continued for '+str(a_state_frames)+' nativeframes since its last change, counted only from your prior controller choices.'
    else:
        meta['next_control_interval_native_frames']=p['cadence_frames'];meta['previous_controls']=records
    state=[_canonical(meta)+p['text_suffix']];clock=frame if p['image_label_clock']=='native_frame' else decision_index
    past=list(previous_images)[-p['maximum_previous_full_screens']:];screens=[(clock,image_png,True)]
    if p['image_order']=='current_first_then_past':screens+= [(f,data,False) for f,data in past]
    else:screens=[(f,data,False) for f,data in past]+screens
    for stamp,data,is_current in screens:
        label=p['current_image_label'] if is_current else p['past_image_label'];state.extend([label.format(clock=stamp),{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(_png(data,p['normalise_png'])).decode()}}])
    if p['crop']:
        native=Image.open(io.BytesIO(image_png)).convert('RGB').resize((256,240),Image.Resampling.NEAREST);crop=native.crop(tuple(p['crop']['native_box'])).resize(tuple(p['crop']['size']),Image.Resampling.NEAREST);stream=io.BytesIO();crop.save(stream,format='PNG');state.extend([p['crop']['label'],{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()}}])
    return {'model':p['model'],'provider':copy.deepcopy(p['provider']),'questions':copy.deepcopy(p['questions']),'state':state}

def decode_profile_response(profile_id,response):
    """Expand the model's exact native choices into simultaneous buttons."""
    p=PROFILES[profile_id];answers=response.get('answers',{})
    for name,q in p['questions'].items():
        a=answers.get(name,{})
        if a.get('type')!='choice' or a.get('choice') not in q['criteria'] or set(a.get('probabilities',{}))!=set(q['criteria']):raise ValueError('Invalid native decision')
    if p['controller_interface']=='explicit_joint_A_B_states':
        direction,_,run,_,jump=answers['action']['choice'].split('_');buttons=dict(horizontal=direction,vertical='released',run=run,jump=jump)
    else:buttons={name:answer['choice'] for name,answer in answers.items()}
    return _buttons(buttons)
