import sys
import subprocess
import os

def run(cmd):
    print("> " + " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    try:
        import uv  # type: ignore
        print("[install] Using uv to sync environment")
        # try to run uv as a module; falls back to CLI if needed
        try:
            run([sys.executable, "-m", "uv", "sync"])
        except Exception:
            # fallback to calling `uv` directly
            run(["uv", "sync"])
        return
    except Exception:
        print("[install] uv not found, using venv + pip")

    # Build a list of candidate commands to create a virtualenv.
    # Avoid using sys.executable when it points inside a missing .venv (common in VSCode setups).
    venv_cmds = []
    try:
        exe_path = os.path.abspath(sys.executable or "")
        if exe_path and os.path.exists(exe_path) and ".venv" not in exe_path:
            venv_cmds.append([sys.executable, "-m", "venv", ".venv"])
    except Exception:
        # ignore issues determining sys.executable
        pass
    venv_cmds.extend([
        ["python3", "-m", "venv", ".venv"],
        ["python", "-m", "venv", ".venv"],
    ])

    created = False
    for cmd in venv_cmds:
        try:
            run(cmd)
            created = True
            break
        except Exception:
            continue

    if not created:
        print("Failed to create virtualenv with attempted commands:", venv_cmds)
        sys.exit(1)

    if os.name == "nt":
        venv_py = os.path.join(".venv", "Scripts", "python.exe")
    else:
        venv_py = os.path.join(".venv", "bin", "python")

    if not os.path.exists(venv_py):
        print("Virtualenv python not found at", venv_py)
        sys.exit(1)

    run([venv_py, "-m", "pip", "install", "-U", "pip"])
    run([venv_py, "-m", "pip", "install", "-r", "requirements.txt"])

if __name__ == "__main__":
    main()
