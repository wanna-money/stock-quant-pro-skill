#!/usr/bin/env python3
"""Environment setup and dependency checker for stock-quant-pro."""
import subprocess
import sys
import importlib

REQUIRED = {
    "akshare": "akshare",
    "pandas": "pandas",
    "numpy": "numpy",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "mplfinance": "mplfinance",
    "quantstats": "quantstats",
}

OPTIONAL_GROUPS = {
    "ta-lib": {"talib": "ta-lib"},
    "pandas-ta": {"pandas_ta": "pandas-ta"},
}


def check_python_version():
    v = sys.version_info
    if v < (3, 10):
        print(f"[FAIL] Python {v.major}.{v.minor} detected. Requires 3.10+")
        return False
    print(f"[OK]   Python {v.major}.{v.minor}.{v.micro}")
    return True


def check_package(import_name: str) -> bool:
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def install_packages(packages: dict[str, str]) -> list[str]:
    failed = []
    for import_name, pip_name in packages.items():
        if check_package(import_name):
            print(f"[OK]   {pip_name}")
            continue
        print(f"[INST] Installing {pip_name}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name, "-q"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"[OK]   {pip_name} installed")
        else:
            print(f"[FAIL] {pip_name}: {result.stderr.strip()[:200]}")
            failed.append(pip_name)
    return failed


def setup():
    print("=" * 50)
    print("  Stock Quant Pro — Environment Setup")
    print("=" * 50)

    if not check_python_version():
        sys.exit(1)

    print("\n--- Required packages ---")
    failed = install_packages(REQUIRED)

    print("\n--- Technical analysis library ---")
    ta_ok = False
    for group_name, pkgs in OPTIONAL_GROUPS.items():
        if all(check_package(k) for k in pkgs):
            print(f"[OK]   {group_name} already installed")
            ta_ok = True
            break
    if not ta_ok:
        for group_name, pkgs in OPTIONAL_GROUPS.items():
            f = install_packages(pkgs)
            if not f:
                ta_ok = True
                break

    if not ta_ok:
        print("[WARN] No TA library installed — will use pure pandas/numpy fallback")

    print("\n--- Summary ---")
    if failed:
        print(f"[WARN] Failed to install: {', '.join(failed)}")
        print("       Try manually: pip install " + " ".join(failed))
    else:
        print("[OK]   All dependencies ready")

    return len(failed) == 0


if __name__ == "__main__":
    success = setup()
    sys.exit(0 if success else 1)
