#!/usr/bin/env python3
"""
main.py – Brainlife entry point for app-map-retinotopic-connections.

Pipeline:
  1. (Optional) Warp template pRF maps to subject space via ANTs registration.
  2. For each visual area and eccentricity (± polar) bin, filter streamlines
     with tckedit and generate a Track Density Image (TDI) with tckmap.

This version is backward-compatible with both:
  - newer nested config style:
      tractogram
      prf.{eccentricity, polarAngle, varea}
      transformation.{warp, inverse-warp, affine}
  - classic Brainlife flat config style:
      track
      eccentricity, polarAngle, varea
      warp, inverse-warp, affine
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from warp_template_segment_to_subject import (
    run_registration_brain,
    apply_transform_to_map,
)
from map_retinotopic_connections import map_retinotopic_connections


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get(cfg: Optional[dict], key: str, default=None):
    if cfg is None:
        return default
    return cfg.get(key, default)


def _first(cfg: Optional[dict], *keys, default=None):
    """Return the first non-empty/non-null key found in cfg."""
    if cfg is None:
        return default
    for key in keys:
        val = cfg.get(key)
        if val is not None and val != "" and val != "null":
            return val
    return default


def _as_bool(val, default=False):
    """Parse booleans robustly from bool/int/str."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in {"1", "true", "yes", "y"}
    return bool(val)


def _warp_required_maps(
    template_ecc: Path,
    template_varea: Path,
    subject_t1: Path,
    affine: Path,
    inv_warp: Optional[Path],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Warp eccentricity and varea maps from template to subject space."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ecc_out = output_dir / "eccentricity.nii.gz"
    varea_out = output_dir / "varea.nii.gz"

    apply_transform_to_map(
        template_ecc,
        subject_t1,
        affine,
        inv_warp,
        ecc_out,
        interpolation="Linear",
        invert_affine=True,
    )
    apply_transform_to_map(
        template_varea,
        subject_t1,
        affine,
        inv_warp,
        varea_out,
        interpolation="NearestNeighbor",
        invert_affine=True,
    )

    return ecc_out, varea_out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Map retinotopic structural connections (Brainlife app)."
    )
    p.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )
    args = p.parse_args()

    cfg: Optional[dict] = None
    config_path = Path(args.config)
    if config_path.exists():
        cfg = json.loads(config_path.read_text())
    else:
        print(f"[WARN] config.json not found at {config_path}; using defaults / CLI only.")

    # ------------------------------------------------------------------
    # 1. Input tractogram (required)
    #    Supports both:
    #      - new schema    : tractogram
    #      - Brainlife flat: track
    # ------------------------------------------------------------------
    track_str = _first(cfg, "tractogram", "track")
    if track_str is None:
        raise ValueError(
            "Config must include either 'tractogram' or classic Brainlife 'track'."
        )

    tract_tck = Path(track_str)
    if not tract_tck.exists():
        raise FileNotFoundError(f"Tractogram not found: {tract_tck}")

    # ------------------------------------------------------------------
    # 2. pRF maps (required)
    #    Supports both:
    #      - new schema    : prf.{eccentricity, polarAngle, varea}
    #      - Brainlife flat: eccentricity, polarAngle, varea
    # ------------------------------------------------------------------
    prf_cfg = _get(cfg, "prf") or {}

    ecc_str = _first(prf_cfg, "eccentricity", default=_get(cfg, "eccentricity"))
    pol_str = _first(prf_cfg, "polarAngle", default=_get(cfg, "polarAngle"))
    varea_str = _first(prf_cfg, "varea", default=_get(cfg, "varea"))

    if not ecc_str or not varea_str:
        raise ValueError(
            "Config must provide eccentricity and varea maps "
            "(either under 'prf' or as top-level Brainlife keys)."
        )

    if not Path(ecc_str).exists():
        raise FileNotFoundError(f"pRF eccentricity map not found: {ecc_str}")
    if not Path(varea_str).exists():
        raise FileNotFoundError(f"pRF varea map not found: {varea_str}")

    outdir = Path(_get(cfg, "outdir") or "output")
    outdir.mkdir(parents=True, exist_ok=True)
    prf_dir = outdir / "prf_maps"

    # ------------------------------------------------------------------
    # 3. Determine pRF maps to use:
    #    A) transformation provided -> warp pRF maps to subject space
    #    B) t1_subject + t1_template provided -> compute registration, then warp
    #    C) neither -> use pRF maps directly (assumed subject space)
    #
    #    Supports both:
    #      - new schema    : transformation.{warp, inverse-warp, affine}
    #      - Brainlife flat: warp, inverse-warp, affine
    # ------------------------------------------------------------------
    transform_cfg = _get(cfg, "transformation") or {}

    warp_str = _first(transform_cfg, "warp", default=_get(cfg, "warp"))
    inv_warp_str = _first(
        transform_cfg, "inverse-warp", default=_get(cfg, "inverse-warp")
    )
    affine_str = _first(transform_cfg, "affine", default=_get(cfg, "affine"))

    t1_subject_str = _get(cfg, "t1_subject")
    t1_template_str = _get(cfg, "t1_template")

    subject_t1 = (
        Path(t1_subject_str)
        if t1_subject_str and t1_subject_str != "null"
        else None
    )
    template_t1 = (
        Path(t1_template_str)
        if t1_template_str and t1_template_str != "null"
        else None
    )

    prf_ecc = Path(ecc_str)
    prf_pol = Path(pol_str) if pol_str and pol_str != "null" else None
    prf_varea = Path(varea_str)

    if affine_str and Path(affine_str).exists():
        # Mode A: use provided transformation to warp pRF maps to subject space
        if subject_t1 is None or not subject_t1.exists():
            raise ValueError(
                "Subject T1 ('t1_subject') is required when a transformation is provided."
            )

        affine = Path(affine_str)
        inv_warp = (
            Path(inv_warp_str)
            if inv_warp_str and Path(inv_warp_str).exists()
            else None
        )

        if inv_warp is None and inv_warp_str:
            print("[WARN] Inverse warp field provided but file not found; affine-only warping will be used.")
        elif inv_warp is None:
            print("[WARN] Inverse warp field not found; affine-only warping will be used.")

        print("[INFO] Warping pRF maps to subject space using provided transformation ...")
        if warp_str and Path(warp_str).exists():
            print(f"[INFO] Forward warp found: {warp_str}")
        ecc_map, varea_map = _warp_required_maps(
            template_ecc=prf_ecc,
            template_varea=prf_varea,
            subject_t1=subject_t1,
            affine=affine,
            inv_warp=inv_warp,
            output_dir=prf_dir,
        )

        polar_map = None
        if prf_pol is not None and prf_pol.exists():
            pol_out = prf_dir / "polarAngle.nii.gz"
            apply_transform_to_map(
                prf_pol,
                subject_t1,
                affine,
                inv_warp,
                pol_out,
                interpolation="Linear",
                invert_affine=True,
            )
            polar_map = pol_out
        else:
            print("[INFO] No polar-angle map provided; polar binning will not be available.")

    elif (
        subject_t1 is not None
        and subject_t1.exists()
        and template_t1 is not None
        and template_t1.exists()
    ):
        # Mode B: compute registration from t1_subject and t1_template, then warp
        nthreads = int(_get(cfg, "nthreads") or _get(cfg, "max_parallel") or 1)
        reglib_str = _get(cfg, "reglib") or _get(cfg, "reglib_path")
        reglib = Path(reglib_str) if reglib_str and reglib_str != "null" else None

        reg_dir = outdir / "reg"
        print("[INFO] Registering subject T1 to template T1 ...")
        affine, warp = run_registration_brain(
            subject_t1=subject_t1,
            template_t1=template_t1,
            output_reg_dir=reg_dir,
            max_parallel=nthreads,
            reglib_path=reglib,
        )

        inv_warp_candidate = Path(
            str(affine).replace("0GenericAffine.mat", "1InverseWarp.nii.gz")
        )
        inv_warp = inv_warp_candidate if inv_warp_candidate.exists() else None
        if inv_warp is None:
            print("[WARN] Inverse warp field not found; affine-only warping will be used.")

        print("[INFO] Warping pRF maps to subject space ...")
        ecc_map, varea_map = _warp_required_maps(
            template_ecc=prf_ecc,
            template_varea=prf_varea,
            subject_t1=subject_t1,
            affine=affine,
            inv_warp=inv_warp,
            output_dir=prf_dir,
        )

        polar_map = None
        if prf_pol is not None and prf_pol.exists():
            pol_out = prf_dir / "polarAngle.nii.gz"
            apply_transform_to_map(
                prf_pol,
                subject_t1,
                affine,
                inv_warp,
                pol_out,
                interpolation="Linear",
                invert_affine=True,
            )
            polar_map = pol_out
        else:
            print("[INFO] No polar-angle map provided; polar binning will not be available.")

    else:
        # Mode C: use pRF maps directly (assumed to be in subject space)
        ecc_map = prf_ecc
        polar_map = prf_pol if prf_pol is not None and prf_pol.exists() else None
        varea_map = prf_varea
        print("[INFO] Using provided pRF maps directly (assumed subject space).")

    # ------------------------------------------------------------------
    # 4. Processing parameters
    # ------------------------------------------------------------------
    areas_str = _get(cfg, "visual_areas") or "V1,V2,V3"
    visual_areas = [a.strip() for a in areas_str.split(",") if a.strip()]

    ecc_bins_str = _get(cfg, "ecc_bins") or "0-2,2-4,4-6,6-8,8-90"
    ecc_bins = [b.strip() for b in ecc_bins_str.split(",") if b.strip()]

    polar_bins_str = _get(cfg, "polar_bins") or "all"
    polar_bins = [b.strip() for b in polar_bins_str.split(",") if b.strip()]
    if not polar_bins:
        polar_bins = ["all"]

    ends_only = _as_bool(_get(cfg, "ends_only"), default=True)
    make_tdi = _as_bool(_get(cfg, "make_tdi"), default=True)

    # ------------------------------------------------------------------
    # 5. Map retinotopic connections
    # ------------------------------------------------------------------
    print("[INFO] Mapping retinotopic connections ...")
    print(f"       visual areas : {visual_areas}")
    print(f"       ecc bins     : {ecc_bins}")
    print(f"       polar bins   : {polar_bins}")
    print(f"       ends_only    : {ends_only}")
    print(f"       make_tdi     : {make_tdi}")

    map_retinotopic_connections(
        tract_tck=tract_tck,
        ecc_map=ecc_map,
        polar_map=polar_map,
        varea_map=varea_map,
        visual_areas=visual_areas,
        ecc_bins=ecc_bins,
        polar_bins=polar_bins,
        outdir=outdir,
        ends_only=ends_only,
        make_tdi=make_tdi,
    )

    print("[INFO] Done. Outputs in:", outdir)


if __name__ == "__main__":
    main()
