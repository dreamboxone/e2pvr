# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE.
"""Compile modules using a receiver-matched Python header set and toolchain."""
import argparse
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include", required=True, type=Path)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--strip", required=True)
    parser.add_argument("--cython", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--python-major", choices=("2", "3"), default="2")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists():
        parser.error("Output directory must not already exist")
    output.mkdir(parents=True)
    package = output / "E2PVR"
    package.mkdir()
    generated = output / "objects"
    generated.mkdir()
    for source in sorted((root / "src" / "E2PVR").iterdir()):
        if not source.is_file() or source.suffix in (".pyc", ".pyo"):
            continue
        if source.suffix != ".py" or source.stem in ("__init__", "platform_profile", "worker_main"):
            shutil.copyfile(str(source), str(package / source.name))
            continue
        c_file = generated / (source.stem + ".c")
        subprocess.check_call([args.cython, "-" + args.python_major, "-D", "--module-name",
            "E2PVR." + source.stem, "-o", str(c_file), str(source)])
        library = package / (source.stem + ".so")
        subprocess.check_call([args.compiler, "-shared", "-fPIC", "-O2", "-std=gnu99",
            "-fno-ident", "-U_FORTIFY_SOURCE", "-I" + str(args.include),
            "-I" + str(args.include.parent),
            "-Wno-deprecated-declarations", "-o", str(library), str(c_file)])
        subprocess.check_call([args.strip, "--strip-unneeded", str(library)])
    print(package)


if __name__ == "__main__":
    main()
