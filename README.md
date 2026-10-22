# dtsync

An in-silico testbed for deciding **when an imaging-driven tumour digital twin should be updated**. It simulates
virtual glioblastoma patients, images them with a synthetic MRI model, tracks each patient with a particle-filter
twin, and compares imaging schedules by how many follow-up scans they use, how late they detect progression and how
well the twin forecasts the lesion between scans.

## What is simulated

| Component | Implementation (`dtsync.py`) |
| --- | --- |
| Anatomy | 2D axial slice with grey matter, white matter (diffusivity ratio 0.2), deep grey nuclei, impermeable ventricles and brain boundary (`make_brain`, `face_coeffs`, `Grid`) |
| Ground truth | Proliferation-invasion (Fisher-KPP) model on a 1 mm grid, 0.25-day step, spatially heterogeneous proliferation, chemoradiation from day 35 to 77 as a net log kill, post-treatment growth multiplier (`Patient`) |
| Imaging | 2 mm block average plus smooth noise, FLAIR mask at density 0.16 and T1Gd mask at 0.80; the image of a given patient on a given day is the same for every policy (`Patient.observe`) |
| Twin | Same equation on a 2 mm grid with a 1-day step and uniform proliferation; sequential importance resampling over (D_w, rho, L, gamma) with a Dice-based kernel, adaptive bandwidth and Liu-West shrinkage (`Twin`) |
| Progression | Enhancing area at least 1.25 times the nadir and at least 100 mm^2 above it (`is_prog`) |
| Policies | `static`, `fixed_30/45/60/90/120`, `reactive` (30 or 90 days depending on the last scan, no twin), `trig_<p>` (scan when the twin's predicted probability of progression reaches p, 28 to 120 days apart) (`run_policy`) |

Every patient is fully determined by its seed, and each policy's filter has its own seed derived from the patient
seed and the policy name, so results do not depend on the order in which policies run.

## Install

Python 3.11 or newer.

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt     # Windows
.venv/bin/python -m pip install -r requirements.txt             # Linux or macOS
```

Tested with Python 3.14.0, NumPy 2.5.4, SciPy 1.18.1 and Matplotlib 3.11.2 on Windows 11.

## Reproduce the results

Everything in one go (resumable: finished patients are skipped on a rerun):

```
python run_all.py
```

This runs, in order: a smoke test, the main cohort (200 patients, 256 particles, noise 0.05), a noise check (100
patients, noise 0.10), a particle-count check (40 patients, 512 particles), the runtime benchmark and the analyses.
Progress is written to `logs/run_all.log`. Set `DTSYNC_WORKERS` to change the number of worker processes; results do
not depend on it. On an AMD Ryzen 5 5600H one patient takes about 15 minutes at 256 particles with 8 workers, so the
full pipeline takes roughly 12 hours.

On a laptop, run it with 6 of the 12 logical cores and the safety guard next to it (PowerShell):

```
$env:DTSYNC_WORKERS = "6"
$p = Start-Process .venv\Scripts\python.exe run_all.py -PassThru
.venv\Scripts\python.exe safety_guard.py $p.Id
```

`safety_guard.py` is a backstop that never slows a normal run: it warns at 90% system RAM and stops the run at 95%,
suspends the run while the laptop is on battery (stopping after 240 minutes), and logs RAM, CPU load and the actual
CPU clock to `logs/safety.log` every 10 minutes. Stopped runs resume where they left off.

Individual steps:

```
python run_batch_mp.py --n 200 --P 256 --noise 0.05 --out results/main      # one cohort (per-patient pickles)
python analyze.py results/main figs/main                                    # table with 95% bootstrap CIs, figures,
                                                                            # figs/main/summary.json and patients.csv
python split_scans.py figs/main/patients.csv                                # scans in progressors versus stable patients
python bench.py                                                             # runtime of propagation and assimilation
python fig_framework.py                                                     # figs/paper/fig1_framework
python fig_snapshots.py 2001 trig_0.1                                       # figs/paper/fig2_snapshots
python fig_tracking.py results/main                                          # figs/paper/figS_tracking (optional)
```

The scan-budget versus detection-delay figure is `figs/main/tradeoff.pdf`, produced by `analyze.py`.

## Folder map

| Path | Content |
| --- | --- |
| `dtsync.py` | Model, imaging, particle filter and policies |
| `run_batch.py` | Serial cohort runner and the list of 13 policies |
| `run_batch_mp.py` | Parallel cohort runner (same results as the serial one) |
| `run_all.py` | Full pipeline with logging |
| `analyze.py` | Summary statistics, bootstrap CIs, figures and the per-patient CSV |
| `split_scans.py` | Scan counts split by progression status |
| `bench.py` | Runtime benchmark, writes `figs/bench.json` |
| `safety_guard.py` | RAM, battery and CPU-clock backstop for long runs on a laptop |
| `fig_framework.py`, `fig_snapshots.py`, `fig_tracking.py` | Figures 1 and 2, optional tracking figure |
| `pilot/` | Pilot run (30 patients, 128 particles): `summary.json` and `patients.csv` |
| `figs/` | Analysis outputs per run (`main`, `noise10`, `p512`, `pilot`) and `paper/` figures |
| `docs/RUN_GUIDE_WINDOWS.md` | Step-by-step guide for running the pipeline on a Windows laptop |

`results/` (per-patient pickles) and `logs/` are created by the runs and are not tracked.

## Licence

MIT, see `LICENSE`.

## Citation

Citation to be added.
