#!/usr/bin/env python3
"""
map_retinotopic_connections.py

Core logic for mapping retinotopic connections:
  - Extract ROI masks per visual area and eccentricity (± polar) bin
  - Filter tractogram streamlines that touch each ROI via tckedit
  - Generate Track Density Images (TDI) for each ROI using tckmap
  - Produce a summary CSV of streamline counts per region
"""
from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from typing import List, Optional

import nibabel as nib
import numpy as np


# ---------------------------------------------------------------------------
# Visual area labels (Benson-style, 1-based integer encoding)
# ---------------------------------------------------------------------------
AREA_LABELS = [
    "V1", "V2", "V3", "hV4",
    "VO1", "VO2", "LO1", "LO2",
    "TO1", "TO2", "V3b", "V3a",
]

# Container image used for MRtrix3 commands
MRTRIX_CONTAINER = "docker://gamorosino/tract_align:latest"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _run_silent(cmd: list[str]) -> None:
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def _run_in_container(cmd: list[str]) -> None:
    """Run a command inside the Singularity container."""
    full = [
        "singularity", "exec", "-e", MRTRIX_CONTAINER,
        "micromamba", "run", "-n", "tract_align",
    ] + cmd
    subprocess.run(full, check=True)


def _run_in_container_silent(cmd: list[str]) -> None:
    full = [
        "singularity", "exec", "-e", MRTRIX_CONTAINER,
        "micromamba", "run", "-n", "tract_align",
    ] + cmd
    result = subprocess.run(full, capture_output=True)
    if result.returncode != 0:
        print(f"[WARN] Command returned non-zero exit code {result.returncode}: {cmd[0]}")
        if result.stderr:
            print(f"[WARN] stderr: {result.stderr.decode(errors='replace').strip()}")


def count_streamlines(tck: Path) -> int:
    if not tck.exists() or tck.stat().st_size == 0:
        return 0
    try:
        full = [
            "singularity", "exec", "-e", MRTRIX_CONTAINER,
            "micromamba", "run", "-n", "tract_align",
            "tckinfo", str(tck), "-count",
        ]
        out = subprocess.check_output(full, stderr=subprocess.DEVNULL).decode().strip()
        return int(out.split()[-1])
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Mask utilities
# ---------------------------------------------------------------------------

def extract_visual_area_mask(varea_img: Path, area_name: str, out_path: Path) -> Path:
    """Binary mask for a named visual area from a Benson-style varea map."""
    if out_path.exists():
        return out_path
    if area_name not in AREA_LABELS:
        raise ValueError(f"Unknown area '{area_name}'. Valid: {AREA_LABELS}")
    val = AREA_LABELS.index(area_name) + 1
    img = nib.load(str(varea_img))
    data = img.get_fdata()
    mask = (np.abs(data - val) < 0.5).astype(np.uint8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(mask, img.affine, img.header), str(out_path))
    return out_path


def _make_ecc_mask(ecc_map: Path, lo: float, hi: float, out_path: Path) -> Path:
    """Binary mask for eccentricity values in [lo, hi]."""
    if out_path.exists():
        return out_path
    img = nib.load(str(ecc_map))
    data = img.get_fdata()
    mask = ((data >= lo) & (data <= hi)).astype(np.uint8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(mask, img.affine, img.header), str(out_path))
    return out_path


def _make_polar_mask(polar_map: Path, lo: float, hi: float, out_path: Path) -> Path:
    """Binary mask for |polar angle| values in [lo, hi]."""
    if out_path.exists():
        return out_path
    img = nib.load(str(polar_map))
    data = np.abs(img.get_fdata())
    mask = ((data >= lo) & (data <= hi)).astype(np.uint8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(mask, img.affine, img.header), str(out_path))
    return out_path


def intersect_masks(mask1: Path, mask2: Path, out_path: Path) -> Path:
    """Element-wise AND of two binary masks."""
    if out_path.exists():
        return out_path
    m1_img = nib.load(str(mask1))
    m2_img = nib.load(str(mask2))
    m1 = np.squeeze(m1_img.get_fdata()) > 0
    m2 = np.squeeze(m2_img.get_fdata()) > 0
    min_shape = tuple(np.minimum(m1.shape, m2.shape))
    slicer = tuple(slice(0, s) for s in min_shape)
    inter = (m1[slicer] & m2[slicer]).astype(np.uint8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(inter, m1_img.affine, m1_img.header), str(out_path))
    return out_path


def _parse_range(rng: str) -> tuple[float, float]:
    """Parse '0-2' or '0_2' into (0.0, 2.0)."""
    rng = rng.strip().replace("_", "-")
    lo, hi = rng.split("-")
    return float(lo), float(hi)


# ---------------------------------------------------------------------------
# tckedit  (streamline filtering)
# ---------------------------------------------------------------------------

def run_tckedit(
    track: Path,
    roi: Path,
    out_tck: Path,
    ends_only: bool = True,
) -> int:
    """
    Filter streamlines from *track* that pass through (or end in) *roi*.
    Returns the number of streamlines written to *out_tck*.
    """
    out_tck.parent.mkdir(parents=True, exist_ok=True)
    if out_tck.exists():
        return count_streamlines(out_tck)

    cmd = [
        "tckedit", str(track), str(out_tck),
        "-include", str(roi),
    ]
    if ends_only:
        cmd.append("-ends_only")

    _run_in_container_silent(cmd)
    return count_streamlines(out_tck)


# ---------------------------------------------------------------------------
# tckmap  (Track Density Image)
# ---------------------------------------------------------------------------

def run_tckmap(
    tck: Path,
    reference: Path,
    out_tdi: Path,
    template: Optional[Path] = None,
) -> Path:
    """
    Generate a Track Density Image (TDI) from *tck* using *reference* as the
    voxel grid.  If a *template* NIfTI is given its header is used instead.
    """
    out_tdi.parent.mkdir(parents=True, exist_ok=True)
    if out_tdi.exists():
        return out_tdi

    ref = template if template is not None else reference
    cmd = [
        "tckmap", str(tck),
        str(out_tdi),
        "-template", str(ref),
    ]
    _run_in_container_silent(cmd)
    return out_tdi


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def map_retinotopic_connections(
    tract_tck: Path,
    ecc_map: Path,
    polar_map: Optional[Path],
    varea_map: Path,
    visual_areas: List[str],
    ecc_bins: List[str],
    polar_bins: List[str],
    outdir: Path,
    ends_only: bool,
    make_tdi: bool,
) -> Path:
    """
    For each visual area and each eccentricity (± polar angle) bin:
      1. Build an ROI mask = visual_area ∩ ecc_bin [∩ polar_bin]
      2. Filter streamlines touching that ROI via tckedit
      3. Optionally generate a TDI of those streamlines

    Writes a summary CSV to outdir/summary.csv.
    Returns the path to the summary CSV.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    roi_dir = outdir / "ROIs"
    tck_dir = outdir / "tcks"
    tdi_dir = outdir / "tdi"
    roi_dir.mkdir(exist_ok=True)
    tck_dir.mkdir(exist_ok=True)
    if make_tdi:
        tdi_dir.mkdir(exist_ok=True)

    summary_rows: list[dict] = []

    for area in visual_areas:
        # area mask
        area_mask = extract_visual_area_mask(
            varea_map, area, roi_dir / f"{area}.nii.gz"
        )

        for ecc_bin in ecc_bins:
            ecc_lo, ecc_hi = _parse_range(ecc_bin)
            ecc_tag = ecc_bin.replace("-", "_")

            ecc_mask = _make_ecc_mask(
                ecc_map, ecc_lo, ecc_hi,
                roi_dir / f"ecc_{ecc_tag}.nii.gz",
            )

            for polar_bin in polar_bins:
                if polar_bin.lower() == "all":
                    polar_tag = "all"
                    roi_mask = intersect_masks(
                        ecc_mask, area_mask,
                        roi_dir / f"{area}_ecc{ecc_tag}.nii.gz",
                    )
                else:
                    if polar_map is None:
                        raise ValueError(
                            "polar_map must be provided when polar_bins != ['all']"
                        )
                    pol_lo, pol_hi = _parse_range(polar_bin)
                    polar_tag = polar_bin.replace("-", "_")
                    pol_mask = _make_polar_mask(
                        polar_map, pol_lo, pol_hi,
                        roi_dir / f"polar_{polar_tag}.nii.gz",
                    )
                    # ecc ∩ polar
                    ecc_pol_mask = intersect_masks(
                        ecc_mask, pol_mask,
                        roi_dir / f"ecc{ecc_tag}_polar{polar_tag}.nii.gz",
                    )
                    # ecc ∩ polar ∩ area
                    roi_mask = intersect_masks(
                        ecc_pol_mask, area_mask,
                        roi_dir / f"{area}_ecc{ecc_tag}_polar{polar_tag}.nii.gz",
                    )

                label = f"{area}_ecc{ecc_tag}_polar{polar_tag}"
                out_tck = tck_dir / f"{label}.tck"

                n = run_tckedit(tract_tck, roi_mask, out_tck, ends_only=ends_only)
                print(f"  [{label}]  streamlines = {n}")

                row = {
                    "visual_area": area,
                    "ecc_bin": ecc_bin,
                    "polar_bin": polar_bin,
                    "n_streamlines": n,
                    "tck": str(out_tck),
                }

                if make_tdi and out_tck.exists() and n > 0:
                    tdi_out = tdi_dir / f"{label}_tdi.nii.gz"
                    run_tckmap(out_tck, ecc_map, tdi_out)
                    row["tdi"] = str(tdi_out)
                else:
                    row["tdi"] = ""

                summary_rows.append(row)

    # Write summary CSV
    csv_path = outdir / "summary.csv"
    fieldnames = ["visual_area", "ecc_bin", "polar_bin", "n_streamlines", "tck", "tdi"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"[INFO] Summary written to {csv_path}")
    return csv_path
