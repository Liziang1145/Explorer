import json
from pathlib import Path
import numpy as np
import torch
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
from lerobot.policies.factory import make_pre_post_processors

model_path = Path('/home/apex/outputs/smolvla_cup_v1_100steps/checkpoints/000100/pretrained_model')
ds = LeRobotDataset('local/cup_pick_v1', root='/home/apex/datasets/lerobot/cup_pick_v1')
policy = SmolVLAPolicy.from_pretrained(model_path).to('cpu').eval()
preprocessor, postprocessor = make_pre_post_processors(policy.config, pretrained_path=str(model_path))
indices = [0, 50, 100, 150, 200]
results = []
with torch.inference_mode():
    for index in indices:
        sample = ds[index]
        batch = {
            'observation.images.head': sample['observation.images.head'].unsqueeze(0),
            'observation.state': sample['observation.state'].unsqueeze(0),
            'task': [sample['task']],
        }
        chunk = postprocessor(policy.predict_action_chunk(preprocessor(batch)))[0].cpu().numpy()
        assert chunk.shape == (50, 7), chunk.shape
        assert np.isfinite(chunk).all(), index
        delta = np.diff(chunk, axis=0)
        results.append({
            'dataset_index': index,
            'shape': list(chunk.shape),
            'finite': True,
            'min_per_dim': chunk.min(axis=0).tolist(),
            'max_per_dim': chunk.max(axis=0).tolist(),
            'max_abs_step_delta_per_dim': np.abs(delta).max(axis=0).tolist(),
            'first_action': chunk[0].tolist(),
            'last_action': chunk[-1].tolist(),
            'gripper_range': [float(chunk[:, 6].min()), float(chunk[:, 6].max())],
        })
stats = ds.meta.stats['action']
report = {
    'model': str(model_path),
    'offline_only': True,
    'samples': results,
    'training_action_min': np.asarray(stats['min']).tolist(),
    'training_action_max': np.asarray(stats['max']).tolist(),
}
out = model_path.parent / 'offline_prediction_report.json'
out.write_text(json.dumps(report, indent=2))
print(json.dumps(report, ensure_ascii=False))
print('report', out)
