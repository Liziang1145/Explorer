import json
from pathlib import Path
import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset

root = Path('/home/apex/datasets/lerobot/cup_pick_v1')
ds = LeRobotDataset('local/cup_pick_v1', root=root)
assert len(ds) == 3098, len(ds)
assert ds.num_episodes == 13, ds.num_episodes
image_shapes = set()
state_shapes = set()
action_shapes = set()
for index in range(len(ds)):
    frame = ds[index]
    image = frame['observation.images.head'].detach().cpu().numpy()
    state = frame['observation.state'].detach().cpu().numpy()
    action = frame['action'].detach().cpu().numpy()
    image_shapes.add(tuple(image.shape))
    state_shapes.add(tuple(state.shape))
    action_shapes.add(tuple(action.shape))
    assert image.size and np.isfinite(image).all(), f'invalid image at {index}'
    assert state.shape == (7,) and np.isfinite(state).all(), f'invalid state at {index}'
    assert action.shape == (7,) and np.isfinite(action).all(), f'invalid action at {index}'
info = json.loads((root / 'meta/info.json').read_text())
summary = json.loads((root / 'conversion_summary.json').read_text())
assert info['fps'] == 5
assert info['total_episodes'] == 13
assert info['total_frames'] == 3098
assert summary['task'] == 'Pick up the cup.'
assert len(summary['episodes']) == 13
assert sum(item['frames'] for item in summary['episodes']) == 3098
print(json.dumps({
    'ok': True,
    'episodes': ds.num_episodes,
    'frames': len(ds),
    'fps': info['fps'],
    'image_shapes_CHW': sorted(image_shapes),
    'state_shapes': sorted(state_shapes),
    'action_shapes': sorted(action_shapes),
    'task': summary['task'],
    'keys': sorted(ds[0].keys()),
    'all_frames_decoded_and_finite': True,
}, ensure_ascii=False))
