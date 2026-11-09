# 2026-11-04 — Resume clip-c2 and the Mapillary import, paused again

## Intent

Resume clip-c2 (paused after epoch 2 of 3) and the Mapillary import on the desktop, then score
clip-c2 on the GeoGuessr-style benchmark. kulo stopped the session after a few minutes to use
the PC, so both were paused again before any result.

## Evidence

- `git checkout main; git pull origin main`: PRs #17–#19 in, `main` at `ff4c12a`.
- clip-c2's original command was run from the old `geolearn-routec` checkout and recorded only in
  an earlier session. It is now kept as a script that runs it from this checkout (so the export
  gets the `country-clip-b16` id) with `--version 0.2.0 --resume`:
  `%LOCALAPPDATA%\geo-companion\training\resume-clip-c2.ps1`, log
  `training\logs\clip-c2-resume.log`. `--init-from` is written with the same mixed slashes as in
  `config.json` so the resume settings check matches.
- The import has its own script, `%LOCALAPPDATA%\geo-companion\resume-mapillary.ps1` (log appended
  to `mapillary-import.log`).
- Both were started hidden (`Start-Process powershell -WindowStyle Hidden -File <script>`). The
  import resumed and reached 2,127 of 5,665 seeds searched. clip-c2 was still loading data (no
  log output yet) when both were stopped with `taskkill /T /F`, about 5 minutes in.
- After the stop: no `geo-train` or Python processes left; `runs\clip-c2\last.pt` (epoch 2,
  2026-11-03 21:41) is untouched, so epoch 3 starts over on resume.
- Both scripts live in the Claude app's virtualized AppData. From kulo's own shell they are under
  `C:\Users\kulo\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\geo-companion\`.
- No code changed; no checks run.

## Limitations

- clip-c2 not scored yet; the `--resume` from the `main` checkout is not yet seen past the
  settings check.
- `mapillary-import.log` mixes encodings (PowerShell 5.1 `Out-File -Append`); count progress with
  the lines of `datasets\mapillary\raw\searched.jsonl` instead.

## Next step

Run both scripts again while kulo is at the PC (clip-c2 needs about 35 minutes), then regrade
clip-c2 on the benchmark and switch `play-clip.ps1` if it beats clip-c1's 63.8% top-1.
