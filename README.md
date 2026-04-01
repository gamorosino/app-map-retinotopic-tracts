# Map Retinotopic Connections (app-map-retinotopic-tracts)

`app-map-retinotopic-tracts` extracts **retinotopically-defined white-matter pathways**
from a **template tractogram** and maps them into **subject space**.

The app implements a simple two-step pipeline:

1. **Template segmentation**

   * Extract streamlines connecting two visual areas (e.g. V1 ↔ V2)
   * Optionally restrict by eccentricity and polar-angle bins
   * Uses MRtrix3 `tckedit`

2. **Warp to subject space**

   * Register subject T1 to template T1 (ANTs) *or* reuse precomputed transforms
   * Warp the segmented tract into subject space

---

## Repository contents

| File / Directory                      | Purpose                                                       |
| ------------------------------------- | ------------------------------------------------------------- |
| `main`                                | Bash entry point (Brainlife-style; reads `config.json`)       |
| `main.py`                             | Python orchestrator (runs segmentation + warping)             |
| `extract_template_tract_segment.py`   | Extracts template-space tract segments                        |
| `warp_template_segment_to_subject.py` | Warps segmented tract to subject space                        |
| `libraries/`                          | Bash libraries (`REGlib.sh`, etc.) used for ANTs registration |

---

## Author

**Gabriele Amorosino**
[gabriele.amorosino@utexas.edu](mailto:gabriele.amorosino@utexas.edu)

---

## Usage

### Brainlife

Run as a standard Brainlife app.

### Local

```bash
git clone https://github.com/gamorosino/app-map-retinotopic-tracts.git
cd app-map-retinotopic-tracts
chmod +x main
./main
```

---

## Inputs (`config.json`)

### Required

| Field         | Description                            |
| ------------- | -------------------------------------- |
| `track`       | Template occipital tractogram (`.tck`) |
| `t1_subject`  | Subject T1 image                       |
| `t1_template` | Template T1 image                      |
| `Va`          | First visual area (e.g. `V1`)          |
| `Vb`          | Second visual area (e.g. `V2`)         |

---

### Optional selection parameters

| Field        | Default | Description                      |
| ------------ | ------- | -------------------------------- |
| `ecc_bin`    | `"all"` | Eccentricity bin (e.g. `0-16`)   |
| `polar_bin`  | `"all"` | Polar angle bin (e.g. `165-180`) |
| `hemisphere` | `"all"` | `L`, `R`, or `all`               |
| `ends_only`  | `true`  | Use `tckedit -ends_only`         |
| `roi_order`  | `true`  | Use ordered ROI filtering        |

---

### Registration options

| Field      | Description                             |
| ---------- | --------------------------------------- |
| `affine`   | Precomputed affine transform (optional) |
| `warp`     | Precomputed warp field (optional)       |
| `nthreads` | Number of threads (default: 1)          |

If `affine` and `warp` are provided → **registration is skipped**.
Otherwise → ANTs registration is computed automatically.

---

### Output

| Field    | Default   |
| -------- | --------- |
| `outdir` | `output/` |

---

## Outputs

```
output/
├── visual_tracts/
│   └── V1_V2_ecc0_16_pol165_180_R.tck     # template segment
│
├── subj_*.tck                             # warped tract in subject space
│
├── Reg2MNI/                               # registration outputs (if computed)
│   ├── *_0GenericAffine.mat
│   ├── *_1Warp.nii.gz
│   └── *_1InverseWarp.nii.gz
│
└── work/
    └── atlas_segment_masks/               # intermediate ROI masks
```

---

## Example config

```json
{
  "track": "input/occipital_template.tck",
  "t1_subject": "input/sub_t1.nii.gz",
  "t1_template": "input/template_t1.nii.gz",

  "Va": "V1",
  "Vb": "V2",

  "ecc_bin": "0-16",
  "polar_bin": "165-180",
  "hemisphere": "R",

  "ends_only": true,
  "roi_order": true,

  "nthreads": 8,
  "outdir": "output"
}
```

---

## Pipeline details

### Step 1 — Template segmentation

Uses:

```
extract_template_tract_segment.py
```

* Builds ROI masks from:

  * Benson atlas (`eccentricity`, `polar angle`, `varea`)
* Extracts streamlines via:

  * `tckedit`
* Supports:

  * eccentricity filtering
  * polar filtering
  * hemisphere restriction

---

### Step 2 — Warp to subject

Uses:

```
warp_template_segment_to_subject.py
```

* Runs ANTs registration (`registration_brain`) via `REGlib.sh`
* Applies transforms to tractogram:

  * `ConvertTransformFile`
  * `scil_apply_transform_to_tractogram.py`

---

## Dependencies

* MRtrix3 (`tckedit`, `tckinfo`)
* ANTs
* scilpy
* nibabel / numpy
* Bash + `REGlib.sh`

---

## Notes

* Input tractogram must be in **template space (MNI)**
* Atlas masks are expected under:

```
data/templates/freesurfer/mri/benson14/
data/templates/hemisphere_parc/
```

(or overridden via CLI)

---

## Citation

If you use this app in your research, please cite:

- **Brainlife.io**: Hayashi, S., et al. (2024). *Nature Methods, 21*(5), 809–813.
  DOI: [10.1038/s41592-024-02237-2](https://doi.org/10.1038/s41592-024-02237-2)
- **MRtrix3**: Tournier, J.-D., et al. (2019). *NeuroImage, 202*, 116137.
  DOI: [10.1016/j.neuroimage.2019.116137](https://doi.org/10.1016/j.neuroimage.2019.116137)
- **ANTs**: Avants, B. B., et al. (2011). *NeuroImage, 54*(3), 2033–2044.
  DOI: [10.1016/j.neuroimage.2010.09.025](https://doi.org/10.1016/j.neuroimage.2010.09.025)
