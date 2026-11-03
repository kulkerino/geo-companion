# 2026-11-03: pretrained network option (route C)

## Why

M1c scores 64.5% top-1 on OSV-5M dashcam photos but only 18.6% top-1 on the GeoGuessr-style
benchmark (25.2% on GeoGuessr screenshots, 11.6% on Street View panorama views). It learned
dashcam photos, not GeoGuessr imagery. About 70k GeoGuessr-style training images are too few
to train a network from zero, but plenty to adapt a network that is already pretrained.

## What changed

- `geo-train run --backbone clip-b16 | convnext-t | timm:<name>` builds a pretrained timm
  network with a new country layer. `countrynet` (the default) is the old from-scratch net.
- The network converts the app's ImageNet normalisation into its own inside the model, so
  `model.onnx`, the manifest and the app stay unchanged.
- The country layer learns 10 times faster than the pretrained part.
- `regrade` and `--init-from` read the backbone from the run's `config.json`; fine-tuning
  from a run with another backbone stops with a clear message.
- Paused runs from before this change still resume (missing settings count as defaults).
- New training dependencies: `timm`, and `torchvision` from the same index as `torch`.
