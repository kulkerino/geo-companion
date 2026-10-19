# Model M1 — dataset and from-scratch country classifier

Status: **approved** (2026-10-19: kulo approved the merge, OSV-5M and the download). M1a and
M1d are done; M1b is in progress. Originally drafted 2026-10-16. Nothing in this plan downloads data
or installs packages until kulo approves it in chat. This plan carries out the model part of
Task 6 (and the training-data part of Task 5) in the
[main plan](superpowers/plans/2026-10-05-geoguessr-meta-learning.md).

## Goal

Replace the `dummy-placeholder` provider with a real model, trained from scratch, that predicts
the **country** of a street-level photo. It must return calibrated candidates or abstain, and
publish held-out accuracy that anyone can reproduce. It stays optional and post-answer only,
under the same provider boundary as today (`geo_companion/models.py`).

## Decisions kulo needs to make

| # | Question | Default proposed |
| --- | --- | --- |
| 1 | Merge PR #1 into `main` first? | yes |
| 2 | Dataset: OpenStreetView-5M (OSV-5M)? | yes |
| 3 | First download: about 3 train shards plus the test split, roughly 15 GB (an estimate) | yes |
| 4 | Add PyTorch, torchvision, onnx and onnxruntime as an optional `training` group | yes |
| 5 | Which GPU is in the Windows machine? Its VRAM sets the batch size and resolution | — |

## Dataset: OpenStreetView-5M

- Source: <https://huggingface.co/datasets/osv5m/osv5m>, released by the OSV-5M authors
  (Astruc et al., CVPR 2024). The imagery comes from Mapillary contributors.
- Licence: **CC-BY-SA 4.0** (from the Hugging Face dataset page, read 2026-10-16). Training is
  allowed. Anything redistributed, which includes trained weights if we treat them as an
  adaptation, has to carry attribution and the same licence. We will not redistribute images.
- Size: the page lists 259 GB. The figures below come from the paper and are **not yet checked
  against the files**: about 5.1M images, about 210k of them test images, labels include
  latitude, longitude, country and region, and the test set is drawn from areas kept separate
  from the train set.
- Why this dataset: the images are street-level, close to GeoGuessr; it covers about 225
  countries; it has an official geographically separated test split; and its licence is clear.
  Public availability alone does not count as permission, so the licence is what clears it.

### Rights ledger

Before any download, add `docs/sources/osv5m.json` with every field
[`ethics-boundary.md`](ethics-boundary.md) requires: source, creator, URL, access date, licence,
attribution text, geographic scope, review date, and rights status. Its status starts at
`pending` and becomes `cleared` only when kulo approves it. The training CLI refuses to read a
dataset whose ledger entry is not `cleared`. This uses the same fail-closed rule as active packs.

### Storage

Data goes in the application-data directory (`platformdirs`), under
`datasets/osv5m/{images,metadata}`, never inside this folder. The download is a separate,
explicit CLI command, `geo-train fetch --ledger docs/sources/osv5m.json --train-shards 0-2
--test-shards 0-4`. It verifies each file against the SHA-256 Hugging Face publishes, records
it in `fetch-log.jsonl`, unpacks the images flat, and writes metadata CSVs filtered to the
images present. The first fetch is 10 files, 20.0 GB (each shard holds 50,000 images). No other code path touches the network.

### Splits

- **test:** the official OSV-5M test split. It is touched only for the final report.
- **val:** 5% of the downloaded train images, **grouped by geographic cell** (for example a
  0.1° grid, or a sequence ID if the metadata has one). This stops near-duplicate frames from
  appearing on both sides of the split. The split is a deterministic hash of the group key.
- **classes:** countries with at least N train images (N set from the shard statistics). Other
  countries are kept out of training and reported as "out of label set" during evaluation.

## Model and training

- **Architecture:** a ResNet-18-style CNN with random initialisation and **no pretrained
  weights**, so it really is trained from scratch. It has about 11M parameters and a softmax
  over countries. The input is 224 px; laptop smoke runs use 128 px.
- **Training:** AdamW with cosine decay, label smoothing 0.1, and mixed precision on CUDA.
  Augmentation is random resized crop and colour jitter, with no horizontal flip, because
  flipping reverses driving side and mirrors text. Training uses class-balanced sampling, with
  a fixed seed and the configuration logged.
- **Calibration:** a temperature fitted on val.
- **Abstention:** the threshold on top-1 probability is chosen on val to reach a target
  precision. Abstention is then checked on test, never tuned there.
- **Hardware:** the laptop (Core Ultra 7 155H, Intel Arc, 14 GB RAM) runs tests and a short
  CPU smoke run on a few thousand images. Real runs go on the Windows RTX machine, run by hand
  for now; Task 7 later automates the worker. Checkpoints stay in application data, and the
  audit already forbids `.pt`, `.pth` and `.onnx` in the repository.

## Evaluation report

The report is a deterministic JSON file plus a short Markdown summary. It contains:

- top-1 and top-5 country accuracy on test;
- accuracy by continent and for each country with at least 50 test images;
- expected calibration error (ECE) before and after temperature scaling;
- coverage and selective accuracy at the chosen abstention threshold;
- a majority-class baseline and a "most common country in the continent" baseline, so the
  numbers have context;
- model size on disk and CPU latency for one image on the laptop through onnxruntime.

## Integration with the app

- Export to ONNX. A model manifest (the Task 2 `ModelManifest`, extended where needed) records
  the artifact SHA-256, the class list, temperature, threshold, input size, licence and
  attribution, and the eval summary.
- `OnnxCountryProvider` implements `PredictionProvider` and is selected with
  `GEO_COMPANION_MODEL=onnx:<manifest path>`. The app verifies the hash at startup and refuses
  a mismatch. It never downloads the model.
- **Known gap:** today the provider only sees the starter pack's diagrams, which are drawings,
  not photos. A photo model will be out of distribution on them and should mostly abstain.
  Real use needs photo rounds (cleared images) or photo upload, which is not built yet. M1
  proves the model offline through its report. Photo upload is the natural next milestone.

## Phases

1. **M1a — pipeline without data.** Write the rights-ledger schema and gate, the metadata
   loader, the grouped split, the model, the training loop, calibration, abstention, the eval
   report and ONNX export. All of it is tested on a tiny synthetic image fixture that is
   generated in the tests, never committed as photos. Needs decision 4.
2. **M1b — first real data.** Fetch the approved shards, clear the ledger, compute dataset
   statistics, and run a laptop smoke training. Needs decisions 2 and 3.
3. **M1c — real training.** Run the full training on the RTX machine, then the eval report.
   Independent review at this milestone. Needs decision 5.
4. **M1d — in the app.** Add the ONNX provider, the manifest and hash check, and a test with a
   tiny exported model built in the tests.
