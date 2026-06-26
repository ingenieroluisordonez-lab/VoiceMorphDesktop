import sys, types, torch, re

sys.modules["fairseq"] = types.ModuleType("fairseq")
sys.modules["fairseq.data"] = types.ModuleType("fairseq.data")
fd = types.ModuleType("fairseq.data.dictionary")
class _D: pass
fd.Dictionary = _D
sys.modules["fairseq.data.dictionary"] = fd

cpt = torch.load(
    r"C:\apps\videos\VoiceMorphDesktop\venv\Lib\site-packages\rvc_python\base_model\hubert_base.pt",
    map_location="cpu", weights_only=False)
fs_keys = sorted(cpt["model"].keys())

from transformers import HubertModel
hf = HubertModel.from_pretrained("facebook/hubert-base-ls960",
    cache_dir=r"C:\apps\videos\VoiceMorphDesktop\models\hubert_hf_cache")
hf_keys = sorted(hf.state_dict().keys())

print("=== Fairseq keys sin mapeo obvio ===")
for k in fs_keys:
    if "encoder.layer" not in k and "feature_extractor" not in k and k not in hf_keys:
        print(" FS:", k)

print("=== HuggingFace keys únicos ===")
for k in hf_keys:
    if "encoder.layer" not in k and "feature_extractor" not in k and k not in fs_keys:
        print(" HF:", k)
