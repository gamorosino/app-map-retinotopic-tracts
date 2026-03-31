#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import numpy as np
import nibabel as nib
from pathlib import Path
from filelock import FileLock
from typing import Optional


AREA_LABELS = ['V1','V2','V3','hV4','VO1','VO2','LO1','LO2','TO1','TO2','V3b','V3a']
LABEL_TO_VAL = {lab: i+1 for i, lab in enumerate(AREA_LABELS)}

def safe_write_nifti(out_path: Path, data: np.ndarray, ref_img: nib.Nifti1Image):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(out_path) + ".lock")
    with lock:
        if out_path.exists():
            return
        img = nib.Nifti1Image(data.astype(np.uint8), ref_img.affine, ref_img.header)
        img.set_data_dtype(np.uint8)
        nib.save(img, str(out_path))

def mask_from_range(map_path: Path, lo: float, hi: float, out_path: Path, abs_value=False):
    ref = nib.load(str(map_path))
    data = ref.get_fdata()
    if abs_value:
        data = np.abs(data)
    m = ((data >= lo) & (data <= hi)).astype(np.uint8)
    safe_write_nifti(out_path, m, ref)
    return out_path

def area_mask(varea_path: Path, area: str, out_path: Path):
    if area not in LABEL_TO_VAL:
        raise ValueError(f"Unknown area '{area}'. Valid: {list(LABEL_TO_VAL.keys())}")
    ref = nib.load(str(varea_path))
    data = ref.get_fdata()
    m = (data == LABEL_TO_VAL[area]).astype(np.uint8)
    safe_write_nifti(out_path, m, ref)
    return out_path

def intersect_masks(mask_a: Path, mask_b: Path, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(out_path) + ".lock")
    with lock:
        if out_path.exists():
            return out_path
        A = nib.load(str(mask_a)); B = nib.load(str(mask_b))
        a = np.squeeze(A.get_fdata()) > 0
        b = np.squeeze(B.get_fdata()) > 0
        min_shape = tuple(np.minimum(a.shape, b.shape))
        slicer = tuple(slice(0, m) for m in min_shape)
        a = a[slicer]; b = b[slicer]
        inter = (a & b).astype(np.uint8)
        out = nib.Nifti1Image(inter, A.affine, A.header)
        out.set_data_dtype(np.uint8)
        nib.save(out, str(out_path))
    return out_path

def count_streamlines(tck: Path) -> int:
    if not tck.exists() or tck.stat().st_size == 0:
        return 0
    try:
        out = subprocess.check_output(
            ["tckinfo", str(tck), "-count"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return int(out.split()[-1])
    except Exception:
        return 0


def apply_hemi_to_roi(
    roi: Path,
    hemi: str,
    lh_mask: Path,
    rh_mask: Path,
    out_path: Path,
) -> Path:
    """
    Constrain ROI to hemisphere by:
      L: ROI ∩ LH  and remove any RH overlap
      R: ROI ∩ RH  and remove any LH overlap
      all: return ROI as-is
    """
    hemi = hemi.upper()
    if hemi == "ALL":
        return roi

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(out_path) + ".lock")
    with lock:
        if out_path.exists():
            return out_path

        R = nib.load(str(roi))
        r = np.squeeze(R.get_fdata()) > 0

        LH = np.squeeze(nib.load(str(lh_mask)).get_fdata()) > 0
        RH = np.squeeze(nib.load(str(rh_mask)).get_fdata()) > 0

        min_shape = tuple(np.minimum(r.shape, LH.shape))
        slicer = tuple(slice(0, m) for m in min_shape)
        r = r[slicer]; LH = LH[slicer]; RH = RH[slicer]

        if hemi == "L":
            out = (r & LH & (~RH)).astype(np.uint8)
        elif hemi == "R":
            out = (r & RH & (~LH)).astype(np.uint8)
        else:
            raise ValueError(f"hemi must be all/L/R (got {hemi})")

        img = nib.Nifti1Image(out, R.affine, R.header)
        img.set_data_dtype(np.uint8)
        nib.save(img, str(out_path))

    return out_path


def run_tckedit(
    track: Path,
    roi1: Path,
    roi2: Path,
    out_tck: Path,
    *,
    ends_only: bool = True,
    roi_order: bool = False,
    hemi: str = "all",              # "all" | "L" | "R"
    lh_mask: Optional[Path] = None,
    rh_mask: Optional[Path] = None,
    keep_temps: bool = False,
) -> Path:
    """
    Extract streamlines connecting ROI1 and ROI2 from `track` into `out_tck`.

    - If roi_order=False: uses unordered includes (A↔B) and is direction-invariant.
    - If roi_order=True: runs ordered A→B and B→A, then merges to avoid losing
      streamlines due to arbitrary streamline direction.

    Hemisphere constraint (optional):
      hemi="L": include lh_mask and exclude rh_mask
      hemi="R": include rh_mask and exclude lh_mask
      hemi="all": no constraint
    """

    out_tck.parent.mkdir(parents=True, exist_ok=True)

    # Reuse if already computed
    if out_tck.exists() and out_tck.stat().st_size > 0:
        return out_tck

    hemi = hemi.upper()
    if hemi not in {"ALL", "L", "R"}:
        raise ValueError(f"hemi must be one of: all, L, R (got {hemi})")

    if hemi in {"L", "R"}:
        if lh_mask is None or rh_mask is None:
            raise ValueError("hemi is L/R but lh_mask or rh_mask is None")

    # Helper to build and run one tckedit command
    def _run_one(out_file: Path, ordered: bool, a: Path, b: Path) -> None:
        cmd = ["tckedit", str(track), str(out_file)]

        # Hemisphere constraint
        if hemi == "L":
            cmd += ["-include", str(lh_mask), "-exclude", str(rh_mask)]
        elif hemi == "R":
            cmd += ["-include", str(rh_mask), "-exclude", str(lh_mask)]

        # ROI constraint
        if ordered:
            cmd += ["-include_ordered", str(a), "-include_ordered", str(b)]
        else:
            cmd += ["-include", str(a), "-include", str(b)]

        if ends_only:
            cmd.append("-ends_only")

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if not roi_order:
        # Simple unordered extraction (already A↔B)
        _run_one(out_tck, ordered=False, a=roi1, b=roi2)
        return out_tck

    # Ordered mode: run both directions and merge
    tmp12 = out_tck.with_suffix(".tmp12.tck")
    tmp21 = out_tck.with_suffix(".tmp21.tck")

    # Clean stale temps (optional safety)
    for tmp in (tmp12, tmp21):
        if tmp.exists():
            tmp.unlink()

    _run_one(tmp12, ordered=True, a=roi1, b=roi2)  # ROI1 → ROI2
    _run_one(tmp21, ordered=True, a=roi2, b=roi1)  # ROI2 → ROI1

    # Merge both (note: duplicates may remain; acceptable for counting, but if you
    # need unique streamlines you’d need additional dedup logic)
    subprocess.run(
        ["tckedit", str(tmp12), str(tmp21), str(out_tck)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not keep_temps:
        tmp12.unlink(missing_ok=True)
        tmp21.unlink(missing_ok=True)

    return out_tck

def voxcount(p: Path) -> int:
    return int((nib.load(str(p)).get_fdata() > 0).sum())





def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, type=Path, help="Template occipital tractogram in MNI space (.tck)")
    ap.add_argument("--out-tck", required=True, type=Path, help="Output segmented .tck")

    ap.add_argument("--Va", required=True, help="Area A (e.g., V1)")
    ap.add_argument("--Vb", required=True, help="Area B (e.g., V2)")

    ap.add_argument("--ecc-bin", default="all", help="e.g. 0-1 or 0_1; or 'all'")
    ap.add_argument("--polar-bin", default="all", help="e.g. 0-15 or 0_15; or 'all'")

    ap.add_argument("--benson-dir", type=Path)
    ap.add_argument("--ends-only", action="store_true", help="Use -ends_only in tckedit")
    ap.add_argument("--roi-order", action="store_true", help="Use -include_ordered in tckedit")

    ap.add_argument("--work-dir", type=Path, default=None,
                    help="Where to store generated masks (default: alongside out-tck)")
    ap.add_argument("--hemisphere", choices=["L", "R", "all"], default="all",
                    help="Restrict tract to hemisphere using include/exclude masks (default: all).")
    ap.add_argument("--repo-root", type=Path, default=None,
                    help="Path to VISCONTI_analysis repo root (default: inferred from script location).")

    args = ap.parse_args()

    repo_root = args.repo_root if args.repo_root else Path(__file__).resolve().parents[2]

    benson_dir = args.benson_dir if args.benson_dir else repo_root / "data/templates/freesurfer/mri/benson14"

    ecc_map   = benson_dir / "benson14_eccen.nii.gz"
    polar_map = benson_dir / "benson14_angle.nii.gz"  # you were using angle for polar bins
    varea_map = benson_dir / "benson14_varea.nii.gz"


    hemi_dir = repo_root / "data/templates/hemisphere_parc"
    lh_mask = hemi_dir / "lh_wm_gm.nii.gz"
    rh_mask = hemi_dir / "rh_wm_gm.nii.gz"

    if args.hemisphere != "all":
        if not lh_mask.exists() or not rh_mask.exists():
            raise FileNotFoundError(f"Missing hemisphere masks in: {hemi_dir}")

    for p in [ecc_map, polar_map, varea_map]:
        if not p.exists():
            raise FileNotFoundError(f"Missing atlas map: {p}")


    ecc_tag   = "all" if args.ecc_bin.lower() == "all"   else args.ecc_bin.replace("-", "_")
    polar_tag = "all" if args.polar_bin.lower() == "all" else args.polar_bin.replace("-", "_")
    hemi_tag  = args.hemisphere

    work = args.work_dir if args.work_dir else args.out_tck.parent / "atlas_segment_masks"
    work.mkdir(parents=True, exist_ok=True)

    # --- Area masks
    A_area = area_mask(varea_map, args.Va, work / f"area_{args.Va}.nii.gz")
    B_area = area_mask(varea_map, args.Vb, work / f"area_{args.Vb}.nii.gz")

    # --- Ecc/polar masks
    if args.ecc_bin.lower() == "all":
        A_ecc = None
        B_ecc = None
    else:
        e = args.ecc_bin.replace("-", "_")
        lo, hi = map(float, e.split("_"))
        ecc_mask = mask_from_range(ecc_map, lo, hi, work / f"ecc_{e}.nii.gz", abs_value=False)
        A_ecc = ecc_mask
        B_ecc = ecc_mask

    if args.polar_bin.lower() == "all":
        polar_mask = None
    else:
        a = args.polar_bin.replace("-", "_")
        lo, hi = map(float, a.split("_"))
        polar_mask = mask_from_range(polar_map, lo, hi, work / f"polar_{a}.nii.gz", abs_value=True)

    # --- Build final ROI1 and ROI2
    roiA = A_area
    roiB = B_area

    if A_ecc is not None:
        print('Apply eccentricity filtering...')
        roiA = intersect_masks(roiA, A_ecc, work / f"roiA_{args.Va}_ecc_{ecc_tag}.nii.gz")
        roiB = intersect_masks(roiB, B_ecc, work / f"roiB_{args.Vb}_ecc_{ecc_tag}.nii.gz")
        print("ROI A voxels:", voxcount(roiA))
        print("ROI B voxels:", voxcount(roiB))

    if polar_mask is not None:
        print('Apply polar angle filtering...')
        roiA = intersect_masks(roiA, polar_mask, work / f"roiA_{args.Va}_ecc_{ecc_tag}_polar_{a}.nii.gz")
        roiB = intersect_masks(roiB, polar_mask, work / f"roiB_{args.Vb}_ecc_{ecc_tag}_polar_{a}.nii.gz")
        print("ROI A voxels:", voxcount(roiA))
        print("ROI B voxels:", voxcount(roiB))


    # --- Apply hemisphere to ROIs (so masks themselves carry hemi)
    if args.hemisphere != "all":
        print('Apply hemisphere filtering...')
    roiA = apply_hemi_to_roi(
        roiA, args.hemisphere, lh_mask, rh_mask,
        work / f"roiA_{args.Va}_ecc_{ecc_tag}_polar_{polar_tag}_hemi_{hemi_tag}.nii.gz"
    )
    roiB = apply_hemi_to_roi(
        roiB, args.hemisphere, lh_mask, rh_mask,
        work / f"roiB_{args.Vb}_ecc_{ecc_tag}_polar_{polar_tag}_hemi_{hemi_tag}.nii.gz"
    )
    if args.hemisphere != "all":
        print("ROI A voxels:", voxcount(roiA))
        print("ROI B voxels:", voxcount(roiB))

    # --- Segment tract
    run_tckedit(
        track=args.template,
        roi1=roiA,
        roi2=roiB,
        out_tck=args.out_tck,
        ends_only=args.ends_only,
        roi_order=args.roi_order,
        hemi=args.hemisphere ,              # "all" | "L" | "R"
        lh_mask=lh_mask,
        rh_mask=rh_mask
    )
    # --- Sanity check: streamline count
    n_streamlines = count_streamlines(args.out_tck)

    print(f"✓ Saved segmented tract: {args.out_tck}")
    print(f"🔎 Final streamline count: {n_streamlines}")

    if n_streamlines == 0:
        print("⚠️ WARNING: zero streamlines found.")
        print("   Check ROI overlap (ecc / polar / hemisphere may be too restrictive).")
    elif n_streamlines < 10:
        print("⚠️ WARNING: very few streamlines (<10). Interpret with caution.")


if __name__ == "__main__":
    main()
