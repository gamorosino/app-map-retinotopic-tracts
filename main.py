#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Optional
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------
# config helpers
# ---------------------------------------------------------------------

def _stage_benson_from_config(cfg: dict, repo_root: Path) -> Path:
    """
    Stage eccentricity/polarAngle/varea from config.json into the Benson-style
    directory expected by extract_template_tract_segment.py.
    Returns the staged benson_dir.
    """
    ecc = _required_path(cfg, "eccentricity")
    pol = _required_path(cfg, "polarAngle")
    var = _required_path(cfg, "varea")

    benson_dir = repo_root / "data" / "templates" / "freesurfer" / "mri" / "benson14"
    benson_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        ecc: benson_dir / "benson14_eccen.nii.gz",
        pol: benson_dir / "benson14_angle.nii.gz",
        var: benson_dir / "benson14_varea.nii.gz",
    }

    for src, dst in targets.items():
        if dst.exists():
            continue
        try:
            dst.symlink_to(src.resolve())
        except Exception:
            shutil.copy2(src, dst)

    return benson_dir

def _get(cfg: Optional[dict], key: str, default=None):
    if cfg is None:
        return default
    return cfg.get(key, default)


def _first(cfg: Optional[dict], *keys, default=None):
    if cfg is None:
        return default
    for key in keys:
        val = cfg.get(key)
        if val is not None and val != "" and val != "null":
            return val
    return default


def _as_bool(val, default=False):
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in {"1", "true", "yes", "y"}
    return bool(val)


def _required_path(cfg: dict, *keys: str) -> Path:
    val = _first(cfg, *keys)
    if val is None:
        raise ValueError(f"Missing required config key. Expected one of: {keys}")
    p = Path(val)
    if not p.exists():
        raise FileNotFoundError(f"File not found for {keys}: {p}")
    return p


def _required_str(cfg: dict, *keys: str) -> str:
    val = _first(cfg, *keys)
    if val is None:
        raise ValueError(f"Missing required config key. Expected one of: {keys}")
    return str(val)


# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Brainlife app wrapper: extract template tract segment and warp it to subject space."
    )
    ap.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    cfg = json.loads(cfg_path.read_text())

    # ---------------------------------------------------------------
    # Paths
    # ---------------------------------------------------------------
    repo_root = SCRIPT_DIR
    extract_script = SCRIPT_DIR / "extract_template_tract_segment.py"
    warp_script = SCRIPT_DIR / "warp_template_segment_to_subject.py"
    reglib = repo_root / "libraries" / "REGlib.sh"

    if not extract_script.exists():
        raise FileNotFoundError(f"Missing script: {extract_script}")
    if not warp_script.exists():
        raise FileNotFoundError(f"Missing script: {warp_script}")
    if not reglib.exists():
        raise FileNotFoundError(f"Missing REGlib.sh: {reglib}")

    # ---------------------------------------------------------------
    # Required inputs
    # ---------------------------------------------------------------
    # template occipital tractogram
    template_tract = _required_path(cfg, "template_tract", "tractogram", "track")

    # subject/template anatomy
    subject_t1 = _required_path(cfg, "t1_subject", "subject_t1")
    template_t1 = _required_path(cfg, "t1_template", "template_t1")

    # selection
    Va = _required_str(cfg, "Va", "visual_area_a")
    Vb = _required_str(cfg, "Vb", "visual_area_b")

    # optional but usually present
    subject_id = str(_get(cfg, "subject_id") or _get(cfg, "subject") or "subject")
    ecc_bin = str(_get(cfg, "ecc_bin") or _get(cfg, "ecc") or "all")
    polar_bin = str(_get(cfg, "polar_bin") or _get(cfg, "pol") or "all")
    hemisphere = str(_get(cfg, "hemisphere") or _get(cfg, "H") or "all")

    outdir = Path(_get(cfg, "outdir") or "output")
    outdir.mkdir(parents=True, exist_ok=True)

    work_dir = outdir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    visual_tracts_dir = outdir / "visual_tracts"
    visual_tracts_dir.mkdir(parents=True, exist_ok=True)

    # flags/options
    ends_only = _as_bool(_get(cfg, "ends_only"), default=True)
    roi_order = _as_bool(_get(cfg, "roi_order"), default=True)
    nthreads = int(_get(cfg, "nthreads") or _get(cfg, "max_parallel") or 1)

    # optional reuse of transforms
    affine = _get(cfg, "affine")
    warp = _get(cfg, "warp")
    skip_registration = False
    if affine and warp:
        affine = Path(affine)
        warp = Path(warp)
        if not affine.exists():
            raise FileNotFoundError(f"Affine transform not found: {affine}")
        if not warp.exists():
            raise FileNotFoundError(f"Warp field not found: {warp}")
        skip_registration = True
    else:
        affine = None
        warp = None

    # tags for filenames
    ecc_tag = ecc_bin.replace("-", "_")
    pol_tag = polar_bin.replace("-", "_")
    hemi_tag = hemisphere

    template_segment = visual_tracts_dir / f"{Va}_{Vb}_ecc{ecc_tag}_pol{pol_tag}_{hemi_tag}.tck"
    benson_dir = _stage_benson_from_config(cfg, repo_root)
    # ---------------------------------------------------------------
    # 1) extract template segment
    # ---------------------------------------------------------------
    extract_cmd = [
        "python3",
        str(extract_script),
        "--template", str(template_tract),
        "--Va", Va,
        "--Vb", Vb,
        "--ecc-bin", ecc_bin,
        "--polar-bin", polar_bin,
        "--out-tck", str(template_segment),
        "--hemisphere", hemisphere,
        "--repo-root", str(repo_root),
        "--work-dir", str(work_dir / "atlas_segment_masks"),
    ]
    if ends_only:
        extract_cmd.append("--ends-only")
    if roi_order:
        extract_cmd.append("--roi-order")

    print("[INFO] Running template segmentation...")
    print("[CMD] " + " ".join(extract_cmd))
    subprocess.run(extract_cmd, check=True)

    # ---------------------------------------------------------------
    # 2) warp template segment to subject
    # ---------------------------------------------------------------
    warp_cmd = [
        "python3",
        str(warp_script),
        "--subject-id", subject_id,
        "--subject-t1", str(subject_t1),
        "--template-t1", str(template_t1),
        "--template-tract", str(template_segment),
        "--Va", Va,
        "--Vb", Vb,
        "--ecc-bin", ecc_bin,
        "--polar-bin", polar_bin,
        "--hemisphere", hemisphere,
        "--out-dir", str(outdir),
        "--max-parallel", str(nthreads),
        "--repo-root", str(repo_root),
        "--reglib", str(reglib),
    ]
    if ends_only:
        warp_cmd.append("--ends-only")
    if roi_order:
        warp_cmd.append("--roi-order")
    if skip_registration:
        warp_cmd.extend([
            "--skip-registration",
            "--affine", str(affine),
            "--warp", str(warp),
        ])

    print("[INFO] Running warp to subject space...")
    print("[CMD] " + " ".join(warp_cmd))
    subprocess.run(warp_cmd, check=True)

    print("[INFO] Done.")
    print(f"[INFO] Template segment: {template_segment}")
    print(f"[INFO] Outputs in: {outdir}")


if __name__ == "__main__":
    main()
