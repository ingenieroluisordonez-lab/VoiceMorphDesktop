import sys, types, torch, numpy as np

sys.modules["fairseq"] = types.ModuleType("fairseq")
sys.modules["fairseq.data"] = types.ModuleType("fairseq.data")
fd = types.ModuleType("fairseq.data.dictionary")
class _D: pass
fd.Dictionary = _D
sys.modules["fairseq.data.dictionary"] = fd

cpt = torch.load(
    r"C:\apps\videos\VoiceMorphDesktop\venv\Lib\site-packages\rvc_python\base_model\hubert_base.pt",
    map_location="cpu", weights_only=False)

from transformers import HubertModel
hf = HubertModel.from_pretrained("facebook/hubert-base-ls960",
    cache_dir=r"C:\apps\videos\VoiceMorphDesktop\models\hubert_hf_cache")
hf_state = hf.state_dict()

pairs = [
    ("encoder.layers.0.self_attn.k_proj.weight", "encoder.layers.0.attention.k_proj.weight"),
    ("post_extract_proj.weight", "feature_projection.projection.weight"),
    ("layer_norm.weight", "feature_projection.layer_norm.weight"),
]
for lk, hk in pairs:
    lw = cpt["model"][lk]
    hw = hf_state[hk]
    d = float((lw - hw).abs().max())
    print(f"{lk}: maxdiff={d:.8f}")
