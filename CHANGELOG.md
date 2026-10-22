# Changelog

## 22 Oct 2026

### Fixed: false alarms counted outside the scoring window (`analyze.py`)

Progression events are scored up to day 420 and the simulation runs to day 540, so that a progression late in the
window can still be detected. Missed detections already followed this rule, but false alarms did not: for a patient
without progression by day 420, any detection on any day up to 540 that was not within 30 days of true progression
counted as a false alarm. Most such detections fall in the last weeks of the simulation (days 521 to 537 in the main
run so far), in patients whose true progression is unknown because it lies beyond day 540, so they cannot be
classified. This is the same censoring artifact that the window to day 420 was introduced to remove.

Fix: a detection counts as a false alarm only if it happens on or before day 420
(`det <= d.EVAL_END` in `summarise`). Delays and missed detections are unchanged. No simulation is affected; only
the false-alarm counts produced by `analyze.py` change.

Effect on the pilot (30 patients, recomputed from `pilot/patients.csv`): the five false alarms reported there
(fixed 30 d: 2, fixed 60 d: 2, reactive: 1) were all detections on day 525 in two patients without progression by
day 540, on a single noisy image shared by every policy that scanned that day. Under the corrected rule the pilot has
no false alarms for any policy. `pilot/summary.json` and `figs/pilot/summary.json` are kept as originally produced.

Mechanism of the false alarms that remain: when the enhancing area falls to zero after chemoradiation, the nadir is
zero and the progression rule reduces to a measured enhancing area of at least 100 mm^2; image noise can lift a
region whose true density sits just below the T1Gd threshold over it.

### Added: optional mask clean-up for a supplementary noise sensitivity run (off by default)

`dtsync.CLEAN_MASKS` (default `False`) and `run_batch_mp.py --clean` keep only the largest connected FLAIR region in
each synthetic image and count enhancement only inside it, as a segmentation pipeline would. With the default the
imaging model is unchanged (checked: `observe()` returns exactly the raw thresholded masks). Reason: at noise 0.10 the
uncleaned images carry several hundred mm^2 of scattered false-positive FLAIR, which biases every twin; the
supplementary run tests whether the noise result is driven by this. All main and robustness results use the default.

### Changed: robustness and laptop safety (no effect on results)

- `run_batch_mp.py` writes each patient file under a temporary name and renames it, so a stopped run never leaves a
  partial file.
- `safety_guard.py` (new) watches a running pipeline: RAM warning at 90% and stop at 95%, suspend on battery, and a
  status line with RAM, CPU load and actual clock every 10 minutes in `logs/safety.log`.
- The overnight run uses `DTSYNC_WORKERS=6`. Each patient depends only on its seed, so the number of workers does
  not change any result.

### Changed: figures (appearance only)

- `fig_framework.py` and `fig_snapshots.py` write 12 cm wide figures to `figs/paper/` in Times New Roman with STIX
  maths. In Fig. 2 the true FLAIR outline is drawn in black instead of white, which was not visible on yellow or in
  greyscale.
