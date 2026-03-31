#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent

# ANTs container used across all registration / transform steps
ANTS_CONTAINER = "docker://brainlife/ants:2.2.0-1bc"


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
    reglib_path: Optional[Path] = None,
) -> tuple[Path, Path]:
    """
    Register the subject T1 to the template T1 using ANTs.

    If reglib_path is provided and REGlib.sh is available, it delegates to:
      source REGlib.sh
      registration_brain "$t1" "$template" --outputdir "$out" -s 2 -c "$max_parallel"

    Otherwise it runs ANTs directly.

    Returns:
      (affine_mat, warp_field)   — paths to the affine .mat and nonlinear warp .nii.gz
    """
    output_reg_dir.mkdir(parents=True, exist_ok=True)

    stem = remove_ext(subject_t1)

    # --- Try REGlib.sh if provided ---
    # REGlib.sh's registration_brain names outputs as {stem}_SyN{suffix}
    # (diffeopost = "SyN" from the default diffeo=SyN[0.25] with -s 2)
    if reglib_path is not None and reglib_path.exists():
        reg_prefix = str(output_reg_dir / (stem + "_SyN"))
        affine = Path(reg_prefix + "0GenericAffine.mat")
        warp = Path(reg_prefix + "1Warp.nii.gz")

        if affine.exists() and warp.exists():
            print(f"[INFO] Registration outputs already exist — skipping: {affine}")
            return affine, warp

        print(f"[INFO] Running registration via REGlib.sh: {reglib_path}")
        cmd = (
            f'source "{reglib_path}" && '
            f'registration_brain "{subject_t1}" "{template_t1}" '
            f'--outputdir "{output_reg_dir}" -s 2 -c {max_parallel}'
        )
        run_bash(cmd)
        if affine.exists() and warp.exists():
            return affine, warp
        raise FileNotFoundError(
            f"REGlib.sh registration did not produce expected output: {affine}"
        )

    # --- Direct ANTs registration ---
    prefix = str(output_reg_dir / (stem + "_to_template_"))

    affine = Path(prefix + "0GenericAffine.mat")
    warp = Path(prefix + "1Warp.nii.gz")
    warped = Path(prefix + "Warped.nii.gz")
    inv_warped = Path(prefix + "InverseWarped.nii.gz")

    # --- Skip registration if outputs already exist ---
    if affine.exists() and warp.exists():
        print(f"[INFO] Registration outputs already exist — skipping: {affine}")
        return affine, warp

    print("[INFO] Running ANTs registration (antsRegistration)...")

    convergence_threshold = "1.e-8"
    its = "10000x10000x0"
    percentage = "0.3"
    syn = "100x100x0,-0.01,5"
    sigma = "1x0.5x0vox"
    shrink = "4x2x1"
    sigma_lin = "4x2x1vox"
    shrink_lin = "3x2x1"
    shrink0 = "6x4x2"
    diffeo = "SyN[0.25]"

    f = str(template_t1)
    m = str(subject_t1)

    stage0 = (
        f"-m mattes[ {f},{m},1,32,regular,{percentage} ] "
        f"-t translation[0.1] -c [{its},{convergence_threshold},20] "
        f"-u 1 -s {sigma_lin} -f {shrink0} -l 1"
    )
    stage1 = (
        f"-m mattes[ {f},{m},1,32,regular,{percentage} ] "
        f"-t rigid[0.1] -c [{its},{convergence_threshold},20] "
        f"-u 1 -s {sigma_lin} -f {shrink_lin} -l 1"
    )
    stage2 = (
        f"-m mattes[ {f},{m},1,32,regular,{percentage} ] "
        f"-t affine[0.1] -c [{its},{convergence_threshold},20] "
        f"-u 1 -s {sigma_lin} -f {shrink_lin} -l 1"
    )
    stage3 = (
        f"-m mattes[ {f},{m},0.5,32 ] -m cc[ {f},{m},0.5,4 ] "
        f"-c [ {syn} ] -t {diffeo} -s {sigma} -f {shrink} -l 1 -u 1 -z 1"
    )

    ants_cmd = (
        f"singularity exec -e {ANTS_CONTAINER} "
        f"antsRegistration -d 3 "
        f"-r [{f},{m},1] "
        f"{stage0} "
        f"{stage1} "
        f"{stage2} "
        f"{stage3} "
        f"-o [{prefix},{warped},{inv_warped}] "
        f"--verbose 1 "
        f"--winsorize-image-intensities [0.005,0.995] "
        f"-n {max_parallel}"
    )

    run_bash(ants_cmd)

    if not affine.exists():
        raise FileNotFoundError(
            f"ANTs registration did not produce expected affine: {affine}"
        )

    return affine, warp


def apply_transform_to_map(
    input_map: Path,
    reference: Path,
    affine: Path,
    warp: Optional[Path],
    output_path: Path,
    interpolation: str = "Linear",
    invert_affine: bool = False,
) -> Path:
    """
    Apply ANTs transforms to a NIfTI map (e.g., pRF eccentricity map).

    To warp a map from template → subject space use the *inverse* transforms:
      - invert_affine=True  (inverse of affine)
      - inverse warp field  (passed as warp)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        print(f"[INFO] Output already exists, skipping: {output_path}")
        return output_path

    affine_flag = f"1" if invert_affine else f"0"
    transform_args = f"-t [{affine},{affine_flag}]"

    if warp is not None and warp.exists():
        transform_args = f"-t {warp} " + transform_args

    cmd = (
        f"singularity exec -e {ANTS_CONTAINER} "
        f"antsApplyTransforms -d 3 "
        f"-i {input_map} "
        f"-r {reference} "
        f"{transform_args} "
        f"-o {output_path} "
        f"-n {interpolation}"
    )

    print(f"[INFO] Applying transform: {input_map.name} -> {output_path.name}")
    run_bash(cmd)

    if not output_path.exists():
        raise FileNotFoundError(
            f"antsApplyTransforms did not produce expected output: {output_path}"
        )
    return output_path


def warp_prf_maps_to_subject(
    template_eccentricity: Path,
    template_polar_angle: Path,
    template_varea: Path,
    subject_t1: Path,
    affine: Path,
    inv_warp: Optional[Path],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """
    Warp pRF maps from template space to subject space using the *inverse* of
    the subject→template registration.

    Returns:
      (eccentricity_subj, polar_angle_subj, varea_subj)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    ecc_out = output_dir / "eccentricity.nii.gz"
    pol_out = output_dir / "polarAngle.nii.gz"
    varea_out = output_dir / "varea.nii.gz"

    apply_transform_to_map(
        template_eccentricity, subject_t1, affine, inv_warp,
        ecc_out, interpolation="Linear", invert_affine=True,
    )
    apply_transform_to_map(
        template_polar_angle, subject_t1, affine, inv_warp,
        pol_out, interpolation="Linear", invert_affine=True,
    )
    # varea is a label map — use nearest-neighbor interpolation
    apply_transform_to_map(
        template_varea, subject_t1, affine, inv_warp,
        varea_out, interpolation="NearestNeighbor", invert_affine=True,
    )

    return ecc_out, pol_out, varea_out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Warp template pRF/retinotopic maps to subject space via ANTs registration."
        )
    )
    p.add_argument("--subject-t1", required=True, type=Path, help="Subject T1 image")
    p.add_argument("--template-t1", required=True, type=Path, help="Template T1 image")
    p.add_argument("--template-ecc", required=True, type=Path,
                   help="Template eccentricity map (nii.gz)")
    p.add_argument("--template-polar", required=True, type=Path,
                   help="Template polar angle map (nii.gz)")
    p.add_argument("--template-varea", required=True, type=Path,
                   help="Template varea (visual area label) map (nii.gz)")
    p.add_argument("--outdir", required=True, type=Path,
                   help="Output directory for warped maps")
    p.add_argument("--reg-dir", default=None, type=Path,
                   help="Directory to store registration files (default: outdir/reg)")
    p.add_argument("--nthreads", default=1, type=int,
                   help="Number of parallel threads for ANTs (default: 1)")
    p.add_argument("--reglib", default=None, type=Path,
                   help="Optional path to REGlib.sh (for registration_brain function)")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    reg_dir = args.reg_dir or (args.outdir / "reg")

    print("[INFO] Running brain registration (subject → template)...")
    affine, warp = run_registration_brain(
        subject_t1=args.subject_t1,
        template_t1=args.template_t1,
        output_reg_dir=reg_dir,
        max_parallel=args.nthreads,
        reglib_path=args.reglib,
    )

    # The inverse warp field (template → subject direction).
    # Derive its path from the returned affine so it works for both the
    # REGlib.sh naming ({stem}_SyN) and the direct-ANTs naming ({stem}_to_template_).
    inv_warp_candidate = Path(str(affine).replace("0GenericAffine.mat", "1InverseWarp.nii.gz"))
    inv_warp = inv_warp_candidate if inv_warp_candidate.exists() else None

    print("[INFO] Warping pRF maps to subject space...")
    ecc_subj, pol_subj, varea_subj = warp_prf_maps_to_subject(
        template_eccentricity=args.template_ecc,
        template_polar_angle=args.template_polar,
        template_varea=args.template_varea,
        subject_t1=args.subject_t1,
        affine=affine,
        inv_warp=inv_warp,
        output_dir=args.outdir,
    )

    print("[INFO] Done. Warped pRF maps:")
    print(f"  eccentricity : {ecc_subj}")
    print(f"  polarAngle   : {pol_subj}")
    print(f"  varea        : {varea_subj}")


if __name__ == "__main__":
    main()
