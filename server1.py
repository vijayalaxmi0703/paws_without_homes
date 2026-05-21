from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"
REEXEC_ENV = "PAWS_SERVER1_REEXEC"


def install_requirements() -> None:
    subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])


def candidate_pythons() -> list[Path]:
    candidates: list[Path] = []
    roots = [
        Path.home() / "AppData" / "Local" / "Programs" / "Python",
        Path("C:/Users/vijay/AppData/Local/Programs/Python"),
    ]
    seen: set[Path] = set()

    for root in roots:
        if not root.exists():
            continue
        for python_dir in sorted(root.glob("Python*")):
            python_exe = python_dir / "python.exe"
            flask_dir = python_dir / "Lib" / "site-packages" / "flask"
            if python_exe.exists() and flask_dir.exists() and python_exe not in seen:
                seen.add(python_exe)
                candidates.append(python_exe)

    return candidates


def reexec_with_working_python() -> None:
    current = Path(sys.executable).resolve()
    if os.environ.get(REEXEC_ENV) == "1":
        return

    for python_exe in candidate_pythons():
        if python_exe.resolve() == current:
            continue

        print(f"Current interpreter is missing Flask. Switching to: {python_exe}")
        env = os.environ.copy()
        env[REEXEC_ENV] = "1"
        completed = subprocess.run([str(python_exe), str(Path(__file__).resolve())], env=env)
        raise SystemExit(completed.returncode)


def load_app():
    try:
        from api.index import app
    except ModuleNotFoundError as exc:
        if exc.name != "flask":
            raise

        reexec_with_working_python()

        print("Flask is not installed for this Python interpreter.")
        print("Installing project requirements automatically...")
        try:
            install_requirements()
        except subprocess.CalledProcessError as install_error:
            print(f"Automatic installation failed: {install_error}")
            print("Try one of these commands:")
            print(r"  C:\Users\vijay\AppData\Local\Programs\Python\Python312\python.exe server1.py")
            print(r"  C:\Users\vijay\AppData\Local\Programs\Python\Python310\python.exe server1.py")
            print(f"  {sys.executable} -m ensurepip --upgrade")
            print(f"  {sys.executable} -m pip install -r {REQUIREMENTS_FILE}")
            raise
        from api.index import app

    return app


app = load_app()


if __name__ == "__main__":
    print("Starting Paws Without Homes on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
