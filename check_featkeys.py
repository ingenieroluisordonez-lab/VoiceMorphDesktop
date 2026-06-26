import sys, types, torch

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

print("=== feature_extractor fairseq ===")
for k in sorted(cpt["model"].keys()):
    if "feature_extractor" in k:
        print(f"  {k}: {list(cpt['model'][k].shape)}")

print("=== feature_extractor HF ===")
for k in sorted(hf_state.keys()):
    if "feature_extractor" in k:
        print(f"  {k}: {list(hf_state[k].shape)}")

print("=== encoder.layers.0 fairseq ===")
for k in sorted(cpt["model"].keys()):
    if "encoder.layers.0." in k:
        print(f"  {k}")

print("=== encoder.layers.0 HF ===")
for k in sorted(hf_state.keys()):
    if "encoder.layers.0." in k:
        print(f"  {k}")
