# Map Retinotopic Connections (app-map-retinotopic-connections)

`app-map-retinotopic-connections` generates **volumetric maps of retinotopically-organised
structural connections** from a white-matter tractogram.

For each requested visual area (e.g. V1, V2, V3) and eccentricity bin the app:

1. Builds an ROI mask = visual-area mask ∩ eccentricity bin [∩ polar-angle bin].
2. Filters the tractogram with **MRtrix3 `tckedit`** to keep only streamlines that
   pass through (or end in) that ROI.
3. Optionally generates a **Track Density Image (TDI)** of the filtered streamlines
   with `tckmap`.

If subject-specific pRF maps are not available, the app can first warp
**template retinotopic maps** (eccentricity, polar angle, varea) to subject space
via **ANTs** registration before running the mapping step.

Repository contents:

| File / Directory | Purpose |
|---|---|
| `main` | Bash entry point (Brainlife-style; reads `config.json`) |
| `main.py` | Python CLI orchestrator |
| `warp_template_segment_to_subject.py` | ANTs registration + pRF-map warping to subject space |
| `map_retinotopic_connections.py` | Core logic: ROI masks, tckedit, tckmap |
| `extract_template_tract_segment.py` | Standalone helper: extract streamlines connecting two visual areas from a template tractogram in MNI space |
| `libraries/` | Bash helper libraries (`REGlib.sh`, `IMAGINGlib.sh`, `STRlib.sh`, `FILESlib.sh`, `CPUlib.sh`) used by the ANTs registration step |

---

## Author

**Gabriele Amorosino**
Email: gabriele.amorosino@utexas.edu

---

## Usage

### Running on Brainlife.io

Run the app from the Brainlife UI / CLI as usual.

### Running locally

#### Prerequisites
- Singularity / Apptainer
- `jq`
- A system that can pull `docker://gamorosino/tract_align:latest`
  and `docker://brainlife/ants:2.2.0-1bc`

#### Steps

```bash
git clone https://github.com/gamorosino/app-map-retinotopic-connections.git
cd app-map-retinotopic-connections
chmod +x main
# edit config.json to point at your data
./main
```

---

## Inputs

All parameters are provided via a `config.json` file (Brainlife auto-generates
this at runtime; create it manually for local runs).

### Mandatory

| Field | Description |
|---|---|
| `tractogram` | Input tractogram (`.tck`) |
| `prf.eccentricity` | Eccentricity map (`eccentricity.nii.gz`) |
| `prf.varea` | Visual-area label map (`varea.nii.gz`; Benson-style integers) |

### Optional pRF field

| Field | Description |
|---|---|
| `prf.polarAngle` | Polar-angle map (`polarangle.nii.gz`) — required only when polar binning is used |

---

### Transformation handling

The pRF maps can be in template space or subject space.  The app supports
three modes, selected automatically based on what is supplied:

#### Mode A — pre-computed transformation provided (`transformation`)

Supply a `transformation` object (datatype `neuro/transform/nifti`) containing the
pre-computed FSL-style warp fields.  The app will use these to warp the pRF maps
from template to subject space.

| Field | Description |
|---|---|
| `transformation.warp` | Forward warp field (`warp.nii.gz`) |
| `transformation.inverse-warp` | Inverse warp field (`inverse-warp.nii.gz`) — optional |
| `transformation.affine` | Affine matrix (`affine.txt`) |
| `t1_subject` | Subject T1-weighted image (`nii.gz`) — required for resampling |

---

#### Mode B — compute transformation automatically

Provide both T1 images and the app registers the subject T1 to the template T1
using ANTs, then warps the pRF maps to subject space.

| Field | Description |
|---|---|
| `t1_subject` | Subject T1-weighted image (`nii.gz`) |
| `t1_template` | Template T1-weighted image (`nii.gz`) |

---

#### Mode C — pRF maps already in subject space

If neither a `transformation` nor T1 images are supplied, the pRF maps are used
directly without any warping (assumed to already be in subject space).

---

### Processing parameters (all optional)

| Field | Type | Default | Description |
|---|---|---|---|
| `visual_areas` | string | `"V1,V2,V3"` | Comma-separated visual areas to process |
| `ecc_bins` | string | `"0-2,2-4,4-6,6-8,8-90"` | Comma-separated eccentricity bins (degrees of visual angle) |
| `polar_bins` | string | `"all"` | Polar-angle bins; `"all"` skips polar restriction |
| `ends_only` | bool | `true` | Use `tckedit -ends_only` (streamlines must terminate in ROI) |
| `make_tdi` | bool | `true` | Generate a TDI (Track Density Image) per ROI |
| `outdir` | string | `"output"` | Root output directory |
| `nthreads` | number | `1` | Number of threads for ANTs registration |
| `reglib` | string | `null` | Optional path to `REGlib.sh` for `registration_brain` |

---

### Visual area labels (Benson-style integers)

| Label | Value |
|---|---|
| V1 | 1 |
| V2 | 2 |
| V3 | 3 |
| hV4 | 4 |
| VO1 | 5 |
| VO2 | 6 |
| LO1 | 7 |
| LO2 | 8 |
| TO1 | 9 |
| TO2 | 10 |
| V3b | 11 |
| V3a | 12 |

---

## Outputs

```
output/
├── prf_maps/                       # Warped pRF maps (Mode B only)
│   ├── eccentricity.nii.gz
│   ├── polarAngle.nii.gz
│   └── varea.nii.gz
├── reg/                            # ANTs registration files (Mode B only)
│   ├── *0GenericAffine.mat
│   ├── *1Warp.nii.gz
│   └── *1InverseWarp.nii.gz
├── ROIs/                           # Binary ROI masks per area × bin
│   ├── V1.nii.gz
│   ├── ecc_0_2.nii.gz
│   ├── V1_ecc0_2.nii.gz
│   └── …
├── tcks/                           # Filtered tractograms per ROI
│   ├── V1_ecc0_2_polarall.tck
│   └── …
├── tdi/                            # Track Density Images (if make_tdi=true)
│   ├── V1_ecc0_2_polarall_tdi.nii.gz
│   └── …
└── summary.csv                     # Streamline counts per region
```

---

## Example `config.json`

### Mode A (pre-computed transformation)

```json
{
  "tractogram": "input/tractogram.tck",
  "prf": {
    "eccentricity": "input/eccentricity.nii.gz",
    "polarAngle": "input/polarangle.nii.gz",
    "varea": "input/varea.nii.gz"
  },
  "transformation": {
    "warp": "input/warp.nii.gz",
    "inverse-warp": "input/inverse-warp.nii.gz",
    "affine": "input/affine.txt"
  },
  "t1_subject": "input/t1.nii.gz",
  "visual_areas": "V1,V2,V3",
  "ecc_bins": "0-2,2-4,4-6,6-8,8-90",
  "polar_bins": "all",
  "ends_only": true,
  "make_tdi": true
}
```

### Mode B (compute transformation from T1 images)

```json
{
  "tractogram": "input/tractogram.tck",
  "prf": {
    "eccentricity": "input/eccentricity.nii.gz",
    "polarAngle": "input/polarangle.nii.gz",
    "varea": "input/varea.nii.gz"
  },
  "t1_subject": "input/t1.nii.gz",
  "t1_template": "input/template_t1.nii.gz",
  "visual_areas": "V1,V2,V3",
  "ecc_bins": "0-2,2-4,4-6,6-8,8-90",
  "polar_bins": "all",
  "ends_only": true,
  "make_tdi": true,
  "nthreads": 4
}
```

### Mode C (pRF maps already in subject space)

```json
{
  "tractogram": "input/tractogram.tck",
  "prf": {
    "eccentricity": "input/eccentricity.nii.gz",
    "polarAngle": "input/polarangle.nii.gz",
    "varea": "input/varea.nii.gz"
  },
  "visual_areas": "V1,V2,V3",
  "ecc_bins": "0-2,2-4,4-6,6-8,8-90",
  "polar_bins": "all",
  "ends_only": true,
  "make_tdi": true
}
```

---

## Container execution

This app runs inside:

```bash
singularity exec -e \
  docker://gamorosino/tract_align:latest \
  micromamba run -n tract_align python3 main.py --config config.json
```

ANTs registration (Mode B) additionally uses:

```bash
singularity exec -e docker://brainlife/ants:2.2.0-1bc antsRegistration …
singularity exec -e docker://brainlife/ants:2.2.0-1bc antsApplyTransforms …
```

---

## Standalone utility: `extract_template_tract_segment.py`

This script extracts streamlines connecting **two visual areas** from a
**template tractogram already in MNI space** (no registration needed).
It is useful for pulling out area-to-area pathway segments (e.g. V1↔V2)
from a pre-computed atlas-space tractogram before any subject-level analysis.

### Usage

```bash
python3 extract_template_tract_segment.py \
  --template path/to/template_tractogram.tck \
  --out-tck  path/to/output.tck \
  --Va V1 --Vb V2 \
  [--ecc-bin 0-2] \
  [--polar-bin 0-15] \
  [--benson-dir path/to/benson14/] \
  [--ends-only] \
  [--roi-order] \
  [--hemisphere all|L|R] \
  [--work-dir path/to/masks/] \
  [--repo-root path/to/repo/]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--template` | yes | Template occipital tractogram in MNI space (`.tck`) |
| `--out-tck` | yes | Output segmented tractogram (`.tck`) |
| `--Va` | yes | First visual area (e.g. `V1`) |
| `--Vb` | yes | Second visual area (e.g. `V2`) |
| `--ecc-bin` | no | Eccentricity bin to restrict both ROIs (e.g. `0-2`); `all` skips filtering |
| `--polar-bin` | no | Polar-angle bin to restrict both ROIs (e.g. `0-15`); `all` skips filtering |
| `--benson-dir` | no | Directory containing `benson14_eccen.nii.gz`, `benson14_angle.nii.gz`, `benson14_varea.nii.gz` (defaults to `<repo-root>/data/templates/freesurfer/mri/benson14`) |
| `--ends-only` | no | Pass `-ends_only` to `tckedit` (streamlines must terminate in both ROIs) |
| `--roi-order` | no | Use `-include_ordered` in `tckedit` so both A→B and B→A directions are merged |
| `--hemisphere` | no | Restrict to `L`, `R`, or `all` (default: `all`); requires hemisphere masks in `<repo-root>/data/templates/hemisphere_parc/` |
| `--work-dir` | no | Directory for intermediate mask files (default: alongside `--out-tck`) |
| `--repo-root` | no | Path to repository root (default: inferred from script location) |

> **Note:** `extract_template_tract_segment.py` calls `tckinfo` and `tckedit`
> directly (they must be available on `PATH`) rather than via a Singularity
> container.

---

## Shell libraries (`libraries/`)

The `libraries/` directory contains Bash helper libraries that are sourced
by the REGlib-based registration path:

| File | Purpose |
|---|---|
| `REGlib.sh` | `registration_brain` function — wraps ANTs for whole-brain registration |
| `IMAGINGlib.sh` | General neuroimaging utility functions |
| `STRlib.sh` | String manipulation helpers |
| `FILESlib.sh` | File handling helpers |
| `CPUlib.sh` | CPU / thread count helpers |

These are used automatically when `reglib` is set in `config.json`.

---

## Citation

If you use this app in your research, please cite:

- **Brainlife.io**: Hayashi, S., et al. (2024). *Nature Methods, 21*(5), 809–813.
  DOI: [10.1038/s41592-024-02237-2](https://doi.org/10.1038/s41592-024-02237-2)
- **MRtrix3**: Tournier, J.-D., et al. (2019). *NeuroImage, 202*, 116137.
  DOI: [10.1016/j.neuroimage.2019.116137](https://doi.org/10.1016/j.neuroimage.2019.116137)
- **ANTs**: Avants, B. B., et al. (2011). *NeuroImage, 54*(3), 2033–2044.
  DOI: [10.1016/j.neuroimage.2010.09.025](https://doi.org/10.1016/j.neuroimage.2010.09.025)