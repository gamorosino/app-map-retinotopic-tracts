#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent


def remove_ext(p: Path) -> str:
    """
    Mimic your bash remove_ext for NIfTI:
      foo.nii.gz -> foo
      foo.nii    -> foo
      otherwise  -> stem
    """
    name = p.name
    if name.endswith(".nii.gz"):
        return name[:-7]
    if name.endswith(".nii"):
        return name[:-4]
    return p.stem


def run_bash(cmd: str) -> None:
    subprocess.run(["bash", "-lc", cmd], check=True)


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


def run_registration_brain(
    subject_t1: Path,
    template_t1: Path,
    output_reg_dir: Path,
    max_parallel: int,
    reglib_path: Path,
) -> tuple[Path, Path]:
    """
    Calls:
      source REGlib.sh
      registration_brain "$t1" "$template" --outputdir "$out" -s 2 -c "$max_parallel"

    Then returns:
      AFFINE = <out>/<basename(t1)>_SyN0GenericAffine.mat
      WARP   = <out>/<basename(t1)>_SyN1Warp.nii.gz
    """
    output_reg_dir.mkdir(parents=True, exist_ok=True)

    # Source REGlib + run registration_brain
    cmd = (
        f"source '{reglib_path}' && "
        f"registration_brain '{subject_t1}' '{template_t1}' "
        f"--outputdir '{output_reg_dir}' -s 2 -c {int(max_parallel)}"
    )
    run_bash(cmd)

    base = remove_ext(subject_t1)
    affine = output_reg_dir / f"{base}_SyN0GenericAffine.mat"
    warp = output_reg_dir / f"{base}_SyN1Warp.nii.gz"

    if not affine.exists():
        raise FileNotFoundError(f"Missing affine after registration: {affine}")
    if not warp.exists():
        raise FileNotFoundError(f"Missing warp after registration: {warp}")

    return affine, warp


def warp_tck_template_to_subject(
    tck_in_tpl: Path,
    tck_out_subj: Path,
    subj_ref: Path,
    affine: Path,
    warp: Path,
) -> None:
    """
    Implements your exact warp toolchain:

      ConvertTransformFile 3 AFFINE AFFINE_converted.mat --convertToAffineType
      scil_apply_transform_to_tractogram.py tck_in subj_ref AFFINE_converted tck_out
           --reference subj_ref -f --reverse_operation --in_deformation warp --keep_invalid
    """
    tck_out_subj.parent.mkdir(parents=True, exist_ok=True)
    
    converted_dir = SCRIPT_DIR / "data" / "converted"
    converted_dir.mkdir(parents=True, exist_ok=True)
    
    affine_conv = converted_dir / f"{affine.stem}_converted.mat"
    
    # Convert affine
    subprocess.run(
        ["ConvertTransformFile", "3", str(affine), str(affine_conv), "--convertToAffineType"],
        check=True
    )

    # Apply transform to tractogram (template -> subject space)
    # NOTE: This matches your snippet exactly (uses --inverse and --in_deformation with the inverse warp).
    subprocess.run(
        [
            "scil_apply_transform_to_tractogram.py",
            str(tck_in_tpl),
            str(subj_ref),
            str(affine_conv),
            str(tck_out_subj),
            "--reference", str(subj_ref),
            "-f",
            "--reverse_operation",
            "--in_deformation", str(warp),
            "--keep_invalid",
        ],
        check=True
    )


def main():
    ap = argparse.ArgumentParser(
        description="Segment template occipital tract by (Va,Vb,ecc,polar,hemi) then warp to subject space."
    )

    # --- subject/template
    ap.add_argument("--subject-id", required=True,
                help="Subject identifier used for naming outputs (e.g. 110613)")
    ap.add_argument("--subject-t1", type=Path, required=True)

    ap.add_argument("--template-t1", type=Path, required=True)
    ap.add_argument("--template-tract", type=Path, required=True,
                    help="Occipital template tractogram in template space (.tck)")

    # --- selection
    ap.add_argument("--Va", required=True)
    ap.add_argument("--Vb", required=True)
    ap.add_argument("--ecc-bin", default="all", help="e.g. 8-16 or 8_16 or 'all'")
    ap.add_argument("--polar-bin", default="all", help="e.g. 75-105 or 75_105 or 'all'")

    # --- output
    ap.add_argument("--out-dir", type=Path, required=True)

    # --- reuse transforms
    ap.add_argument("--affine", type=Path, default=None,
                    help="If provided with --warp, skips registration.")
    ap.add_argument("--warp", type=Path, default=None,
                    help="Warp (SyN1Warp.nii.gz).")
    ap.add_argument("--skip-registration", action="store_true",
                    help="Requires --affine and --warp.")

    # --- registration lib + parallelism
    ap.add_argument("--max-parallel", type=int, default=8,
                    help="Passed to registration_brain -c (default: 8)")
    ap.add_argument("--reglib", type=Path, default=None,
                    help="Path to REGlib.sh (default: inferred from repo-root)")

    # --- options mirrored from extract_template_tract_segment.py
    ap.add_argument("--ends-only", action="store_true")
    ap.add_argument("--roi-order", action="store_true")
    ap.add_argument("--hemisphere", choices=["L", "R", "all"], default="all")
    ap.add_argument("--repo-root", type=Path, default=None,
                    help="VISCONTI_analysis repo root (default: inferred).")
    ap.add_argument("--benson-dir", type=Path, default=None,
                    help="Override benson14 dir (default: inferred in callee).")
    ap.add_argument("--work-dir", type=Path, default=None,
                    help="Where to store generated masks for template segmentation.")

    args = ap.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Infer repo_root like you suggested: dirname(dirname(script))
    repo_root = args.repo_root if args.repo_root else Path(__file__).resolve().parents[2]

    # Infer REGlib.sh location if not provided
    reglib_path = args.reglib if args.reglib else (
        repo_root / "code/tractogram_alignment_repo/code/wm_registration/libraries/REGlib.sh"
    )
    if not reglib_path.exists():
        raise FileNotFoundError(f"REGlib.sh not found: {reglib_path}")

    # --------------------------
    # 1) registration transforms
    # --------------------------
    if args.skip_registration:
        if args.affine is None or args.warp is None:
            raise ValueError("--skip-registration requires --affine and --inv-warp")
        affine = args.affine
        warp = args.warp
    else:
        reg_dir = out_dir / "Reg2MNI"
        affine, warp = run_registration_brain(
            subject_t1=args.subject_t1,
            template_t1=args.template_t1,
            output_reg_dir=reg_dir,
            max_parallel=args.max_parallel,
            reglib_path=reglib_path,
        )

    # --------------------------
    # 2) segment template tract
    # --------------------------
    ecc_tag = "all" if args.ecc_bin.lower() == "all" else args.ecc_bin.replace("-", "_")
    pol_tag = "all" if args.polar_bin.lower() == "all" else args.polar_bin.replace("-", "_")
    hemi_tag = args.hemisphere

    tpl_segment = out_dir / f"tpl_{args.Va}_{args.Vb}_ecc{ecc_tag}_pol{pol_tag}_hemi{hemi_tag}.tck"

    cmd = [
        "python",
        str(SCRIPT_DIR / "extract_template_tract_segment.py"),
        "--template", str(args.template_tract),
        "--Va", args.Va,
        "--Vb", args.Vb,
        "--ecc-bin", args.ecc_bin,
        "--polar-bin", args.polar_bin,
        "--out-tck", str(tpl_segment),
        "--hemisphere", args.hemisphere,
    ]
    if args.ends_only:
        cmd.append("--ends-only")
    if args.roi_order:
        cmd.append("--roi-order")
    if args.benson_dir:
        cmd += ["--benson-dir", str(args.benson_dir)]
    if args.work_dir:
        cmd += ["--work-dir", str(args.work_dir)]
    # pass repo-root explicitly so both scripts resolve the same tree
    cmd += ["--repo-root", str(repo_root)]

    subprocess.run(cmd, check=True)

    n_tpl = count_streamlines(tpl_segment)
    print(f" Template segmented tract: {tpl_segment}")
    print(f" Template segment streamline count: {n_tpl}")
    if n_tpl == 0:
        print(" WARNING: template segment has 0 streamlines (ecc/polar/hemi too restrictive?)")

    # --------------------------
    # 3) warp into subject space
    # --------------------------
    subj_segment = out_dir / (
        f"subj_{args.subject_id}_{args.Va}_{args.Vb}_ecc{ecc_tag}_pol{pol_tag}_hemi{hemi_tag}.tck"
    )

    warp_tck_template_to_subject(
        tck_in_tpl=tpl_segment,
        tck_out_subj=subj_segment,
        subj_ref=args.subject_t1,
        affine=affine,
        warp=warp,
    )

    n_subj = count_streamlines(subj_segment)
    print(f" Subject-space segmented tract: {subj_segment}")
    print(f" Subject segment streamline count: {n_subj}")
    if n_subj == 0:
        print(" WARNING: subject-space segment has 0 streamlines (warp or ROI mismatch?)")


if __name__ == "__main__":
    main()
