from pathlib import Path
import os

def load_user_credentials():
    cred_path = Path(os.environ["USERPROFILE"]) / "Documents" / "syn_credentials.txt"

    if not cred_path.exists():
        raise RuntimeError(f"Credential file not found: {cred_path}")

    with cred_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()
