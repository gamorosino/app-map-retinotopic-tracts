<h1 align="center">Map Retinotopic Connections</h1>

<p align="center">
  Extracts the streamlines connecting two visual areas (optionally restricted to eccentricity, polar-angle and hemisphere bins) from a template tractogram using retinotopic maps and MRtrix3 tckedit, and warps the tract into subject space with ANTs.
</p>

<p align="center">
  <a href="https://github.com/brainlife/abcd-spec"><img src="https://img.shields.io/badge/ABCD_Spec-v1.1-green.svg" alt="ABCD Spec v1.1"></a>
  <a href="https://doi.org/10.25663/brainlife.app.913"><img src="https://img.shields.io/badge/Brainlife-brainlife.app.913-blue.svg" alt="Run on brainlife.io"></a>
</p>

## At a glance

<!-- brainlife-app:begin (generated from the App manifest; edit the manifest, not this block) -->

> **Extracts the streamlines connecting two visual areas (optionally restricted to eccentricity, polar-angle and hemisphere bins) from a template tractogram using retinotopic maps and MRtrix3 tckedit, and warps the tract into subject space with ANTs.**

Builds ROI masks of the two visual areas and the requested eccentricity and polar-angle bins from template-space retinotopic maps (Benson-style varea, eccentricity and polar angle), selects the template streamlines connecting them with tckedit (endpoints only and ordered ROIs by default), then maps the selected tract into the subject's space using the given affine and warp or, if they are absent, an ANTs registration of the subject T1 to the template T1. Use it to obtain retinotopically defined visual pathways (e.g. V1-V2 for a given eccentricity band) in a subject without subject-level tractography.

| | |
|---|---|
| **Inputs** | `neuro/track/tck` · `neuro/prf` · `neuro/transform/nifti` · `neuro/anat/t1w` ×2 |
| **Outputs** | `neuro/track/tck` |
| **Container** | `gamorosino/tract_align:latest` |
| **Resources** | 1 CPUs · 4 h walltime |
| **Run it** | [doi.org/10.25663/brainlife.app.913](https://doi.org/10.25663/brainlife.app.913) |

#### Inputs

| Input | Datatype | Required | Description |
|---|---|---|---|
| `tractogram` | `neuro/track/tck` | yes | Template-space (e.g. occipital) tractogram from which the pathway is extracted. |
| `prf` | `neuro/prf` | yes | Template-space retinotopic maps; eccentricity, polarAngle and varea (visual area labels) are used to define the ROIs. Must be in the same space as the template tractogram and template T1. |
| `transform` | `neuro/transform/nifti` | yes | Precomputed affine and warp between template and subject; if both are present, registration is skipped. |
| `t1_template` | `neuro/anat/t1w` | yes | T1-weighted image of the template space. |
| `t1_subject` | `neuro/anat/t1w` | yes | T1-weighted image of the target subject. |

#### Outputs

| Output | Datatype | Description |
|---|---|---|
| `output` | `neuro/track/tck` | Selected tract warped to subject space (.tck), with the template-space segment and registration outputs in the output folder. |

<details>
<summary><b>Parameters</b> (7)</summary>

| Parameter | Type | Default | Description |
|---|---|---|---|
| `visual_area_a` | string | `V1` | First visual area label (e.g. V1). |
| `visual_area_b` | string | `V2` | Second visual area label (e.g. V2). |
| `ecc_bin` | string |  | Eccentricity bin in degrees (e.g. '0-16'); empty means all. |
| `polar_bin` | string |  | Polar angle bin in degrees (e.g. '165-180'); empty means all. |
| `hemisphere` | string |  | Hemisphere to extract: L, R, or empty for both. |
| `ends_only` | boolean | `true` | Require the streamline endpoints (not any point) to be in the ROIs (tckedit -ends_only). |
| `roi_order` | boolean | `true` | Require streamlines to traverse the ROIs in order (ordered ROI filtering). |

</details>

<!-- brainlife-app:end -->

## Running the App

### On brainlife.io

Open the App at [doi.org/10.25663/brainlife.app.913](https://doi.org/10.25663/brainlife.app.913), choose `neuro/track/tck`, `neuro/prf`, `neuro/transform/nifti`, `neuro/anat/t1w`, `neuro/anat/t1w` from your project, set the parameters and press **Execute**. The results are saved to your project as `neuro/track/tck`.

### Locally

You need [Singularity/Apptainer](https://apptainer.org/) (the App runs in `gamorosino/tract_align:latest`), [`jq`](https://jqlang.github.io/jq/).

1. Clone this repository.
2. Create `config.json` with the paths to your inputs and the parameters:

   ```json
   {
       "tractogram": "/path/to/tractogram/tractogram",
       "r2": "/path/to/prf/r2",
       "polarAngle": "/path/to/prf/polarAngle",
       "eccentricity": "/path/to/prf/eccentricity",
       "rfWidth": "/path/to/prf/rfWidth",
       "varea": "/path/to/prf/varea",
       "surfaces": "/path/to/prf/surfaces",
       "prf_surfaces": "/path/to/prf/prf_surfaces",
       "warp": "/path/to/transform/warp",
       "inverse-warp": "/path/to/transform/inverse-warp",
       "affine": "/path/to/transform/affine",
       "t1_template": "/path/to/t1_template/t1_template",
       "t1_subject": "/path/to/t1_subject/t1_subject",
       "visual_area_a": "V1",
       "visual_area_b": "V2",
       "ecc_bin": "",
       "polar_bin": "",
       "hemisphere": "",
       "ends_only": true,
       "roi_order": true
   }
   ```

3. Run `./main`.

## Repository contents

| File / Directory                      | Purpose                                                       |
| ------------------------------------- | ------------------------------------------------------------- |
| `main`                                | Bash entry point (Brainlife-style; reads `config.json`)       |
| `main.py`                             | Python orchestrator (runs segmentation + warping)             |
| `extract_template_tract_segment.py`   | Extracts template-space tract segments                        |
| `warp_template_segment_to_subject.py` | Warps segmented tract to subject space                        |
| `libraries/`                          | Bash libraries (`REGlib.sh`, etc.) used for ANTs registration |

---

## Local

```bash
git clone https://github.com/gamorosino/app-map-retinotopic-tracts.git
cd app-map-retinotopic-tracts
chmod +x main
./main
```

---

## Required

| Field         | Description                            |
| ------------- | -------------------------------------- |
| `track`       | Template occipital tractogram (`.tck`) |
| `t1_subject`  | Subject T1 image                       |
| `t1_template` | Template T1 image                      |
| `Va`          | First visual area (e.g. `V1`)          |
| `Vb`          | Second visual area (e.g. `V2`)         |

---

## Optional selection parameters

| Field        | Default | Description                      |
| ------------ | ------- | -------------------------------- |
| `ecc_bin`    | `"all"` | Eccentricity bin (e.g. `0-16`)   |
| `polar_bin`  | `"all"` | Polar angle bin (e.g. `165-180`) |
| `hemisphere` | `"all"` | `L`, `R`, or `all`               |
| `ends_only`  | `true`  | Use `tckedit -ends_only`         |
| `roi_order`  | `true`  | Use ordered ROI filtering        |

---

## Registration options

| Field      | Description                             |
| ---------- | --------------------------------------- |
| `affine`   | Precomputed affine transform (optional) |
| `warp`     | Precomputed warp field (optional)       |
| `nthreads` | Number of threads (default: 1)          |

If `affine` and `warp` are provided → **registration is skipped**.
Otherwise → ANTs registration is computed automatically.

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

## Step 1 — Template segmentation

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

## Step 2 — Warp to subject

Uses:

```
warp_template_segment_to_subject.py
```

* Runs ANTs registration (`registration_brain`) via `REGlib.sh`
* Applies transforms to tractogram:

  * `ConvertTransformFile`
  * `scil_apply_transform_to_tractogram.py`

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

## Citing

If you use this App, please cite it, the software it builds on and brainlife.io:

- Map Retinotopic Connections. brainlife.io App. [doi:10.25663/brainlife.app.913](https://doi.org/10.25663/brainlife.app.913)
- **MRtrix3**: Tournier, J.-D., et al. (2019). *NeuroImage, 202*, 116137. DOI: [10.1016/j.neuroimage.2019.116137](https://doi.org/10.1016/j.neuroimage.2019.116137)
- **ANTs**: Avants, B. B., et al. (2011). *NeuroImage, 54*(3), 2033–2044. DOI: [10.1016/j.neuroimage.2010.09.025](https://doi.org/10.1016/j.neuroimage.2010.09.025)
- Hayashi S, Caron BA, Heinsfeld AS, et al. brainlife.io: a decentralized and open-source cloud platform to support neuroscience research. *Nature Methods* 21:809–813 (2024). [doi:10.1038/s41592-024-02237-2](https://doi.org/10.1038/s41592-024-02237-2)
- Avesani P, McPherson B, Hayashi S, et al. The open diffusion data derivatives, brain data upcycling via integrated publishing of derivatives and reproducible open cloud services. *Scientific Data* 6:69 (2019). [doi:10.1038/s41597-019-0073-y](https://doi.org/10.1038/s41597-019-0073-y)

## Authors

**Gabriele Amorosino**

---
