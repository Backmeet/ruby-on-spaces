import sys

# --- Critical core module check ---
try:
    import os
    import subprocess
    import base64
    import json
except ImportError:
    print("[✗] Your Python installation is missing core modules.")
    print("[!] This usually means you're using an incomplete or broken embedded Python build.")
    sys.exit(1)

# --- Try to import requests or install it ---
try:
    import requests
except ImportError:
    print("[*] Installing 'requests' module...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "requests"])
        import requests
    except Exception as e:
        print("[✗] Failed to install 'requests'. Try installing Python with pip support.")
        sys.exit(1)

# --- Begin install logic ---
repo = "Backmeet/ruby-on-spaces"
api_url = f"https://api.github.com/repos/{repo}/contents/"

print("[*] Fetching available versions...")
try:
    response = requests.get(api_url)
    response.raise_for_status()
    contents = response.json()
except Exception as e:
    print(f"[✗] Failed to access GitHub API: {e}")
    sys.exit(1)

# --- Parse versions ---
versions = {}
for item in contents:
    if item["type"] == "dir" and item["name"].startswith("ver"):
        versions[item["name"]] = item["url"]

if not versions:
    print("[✗] No version folders (ver*) found in repo.")
    sys.exit(1)

print("Available versions:")
for v in versions:
    print(f"  {v}")

selected_version = input("Which version to install? ").strip()
if selected_version not in versions:
    print(f"[✗] Version '{selected_version}' not found.")
    sys.exit(1)

# --- Get interpret.py ---
try:
    folder_contents = requests.get(versions[selected_version]).json()
    interpret_url = None
    for item in folder_contents:
        if item["name"] == "interpret.py":
            interpret_url = item["url"]
            break
    if not interpret_url:
        print("[✗] interpret.py not found in version folder.")
        sys.exit(1)

    file_data = requests.get(interpret_url).json()
    code = base64.b64decode(file_data["content"]).decode("utf-8")
except Exception as e:
    print(f"[✗] Error fetching file: {e}")
    sys.exit(1)

# --- Get alias name ---
alias = input("Command alias (no extension): ").strip()
if not alias:
    print("[✗] No alias entered.")
    sys.exit(1)

# --- Determine install locations ---
paths_to_try = [
    os.path.expandvars(r"%USERPROFILE%\Scripts"),
    os.path.expandvars(r"%APPDATA%\Python\Scripts"),
    os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Programs", "Python", "Scripts")
]

print("[*] Trying to install to known script folders...")
install_success = False
for path in paths_to_try:
    try:
        os.makedirs(path, exist_ok=True)
        script_path = os.path.join(path, f"{alias}.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"[✓] Installed as: {script_path}")
        final_dir = path
        install_success = True
        break
    except Exception as e:
        print(f"[!] Could not write to {path}: {e}")

if not install_success:
    print("[✗] Could not install to any known folder. Try running as admin or using a writable directory.")
    sys.exit(1)

# --- Add to PATH ---
print("[*] Checking if install path is already in PATH...")
current_path = os.environ.get("PATH", "")
already_in_path = any(p.lower() == final_dir.lower() for p in current_path.split(os.pathsep))

if already_in_path:
    print("[✓] Install path already in PATH.")
else:
    added = False
    print("[*] Adding to PATH...")

    try:
        subprocess.run(f'setx PATH "%PATH%;{final_dir}"', shell=True)
        print("[+] PATH updated using setx.")
        added = True
    except:
        print("[!] setx failed.")

    if not added:
        try:
            subprocess.run([
                "powershell", "-Command",
                f'[Environment]::SetEnvironmentVariable("Path", "$env:Path;{final_dir}", "User")'
            ], shell=True)
            print("[+] PATH updated using PowerShell.")
            added = True
        except:
            print("[!] PowerShell PATH update failed.")

    if not added:
        print(f"[!] Could not add to PATH automatically.")
        print(f"→ You must add this folder to PATH manually:\n{final_dir}")

# --- Done ---
print("\n[✓] Installation complete.")
print(f"[→] To run: open a new terminal and type: {alias} <args>")
