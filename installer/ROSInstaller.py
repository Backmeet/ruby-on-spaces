import os
import sys
import base64
import json
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# --- Ensure requests ---
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "requests"])
    import requests

# --- Constants ---
REPO = "Backmeet/ruby-on-spaces"
API_URL = f"https://api.github.com/repos/{REPO}/contents/"

# --- Globals ---
version_map = {}
selected_version = ""
alias_name = ""
install_dir = ""

# --- Root window setup ---
root = tk.Tk()
root.title("Ruby on Spaces Installer")
root.geometry("500x400")
root.minsize(500, 400)
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

# --- Page switching ---
def show_frame(frame):
    frame.tkraise()

# --- Utility: log output to a Text box ---
def log(text_widget, msg):
    text_widget.config(state="normal")
    text_widget.insert("end", msg + "\n")
    text_widget.see("end")
    text_widget.config(state="disabled")
    root.update_idletasks()

# --- Page 1: Input ---
page1 = ttk.Frame(root, padding=20)
page1.grid(row=0, column=0, sticky="nsew")
page1.columnconfigure(0, weight=1)
page1.rowconfigure(3, weight=1)

frame_inner = ttk.Frame(page1)
frame_inner.grid(row=1, column=0, sticky="n", pady=40)
frame_inner.columnconfigure(1, weight=1)

ttk.Label(frame_inner, text="Select version:").grid(row=0, column=0, sticky="e", padx=10, pady=10)
version_var = tk.StringVar()
version_dropdown = ttk.Combobox(frame_inner, textvariable=version_var, state="readonly", width=40)
version_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

ttk.Label(frame_inner, text="Command alias:").grid(row=1, column=0, sticky="e", padx=10, pady=10)
alias_entry = ttk.Entry(frame_inner, width=43)
alias_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

next_button = ttk.Button(page1, text="Next ▶")
next_button.grid(row=2, column=0, pady=10)

# --- Page 2: Installer ---
page2 = ttk.Frame(root, padding=10)
page2.grid(row=0, column=0, sticky="nsew")
page2.columnconfigure(0, weight=1)

# Progress bar at the top
progress_var = tk.DoubleVar()
progress = ttk.Progressbar(page2, maximum=100, variable=progress_var)
progress.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

# Filler frame to push debug to bottom
filler_frame = ttk.Frame(page2)
filler_frame.grid(row=1, column=0, sticky="nsew")
page2.rowconfigure(1, weight=1)

# Debug output (short height, fixed to bottom)
debug_frame = ttk.Frame(page2)
debug_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
debug_frame.columnconfigure(0, weight=1)

debug_output = tk.Text(debug_frame, height=6, wrap="word", state="disabled", bg="#f0f0f0")
debug_output.grid(row=0, column=0, sticky="ew")

scrollbar = ttk.Scrollbar(debug_frame, command=debug_output.yview)
debug_output.configure(yscrollcommand=scrollbar.set)
scrollbar.grid(row=0, column=1, sticky="ns")

# --- GitHub version fetch ---
def fetch_versions():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        items = response.json()
        for item in items:
            if item["type"] == "dir" and item["name"].startswith("ver"):
                version_name = item["name"]
                # If it doesn't contain a dot, mark as beta
                if "." not in version_name:
                    version_name += " BETA"
                version_map[version_name] = item["url"]
        version_dropdown["values"] = list(version_map.keys())
    except Exception as e:
        messagebox.showerror("Error", f"Failed to fetch versions: {e}")
        root.quit()

fetch_versions()

# --- Install Logic (page 2) ---
def go_to_install():
    global selected_version, alias_name
    selected_version = version_var.get().strip()
    alias_name = alias_entry.get().strip()

    if not selected_version or not alias_name:
        messagebox.showerror("Input Required", "Please select a version and enter a command alias.")
        return

    show_frame(page2)
    threading.Thread(target=do_install).start()

def do_install():
    global install_dir
    log(debug_output, f"[*] Installing '{selected_version}' as '{alias_name}'...")
    progress_var.set(10)

    try:
        folder_url = version_map[selected_version]
        folder_contents = requests.get(folder_url).json()
        progress_var.set(30)

        py_file = None
        for item in folder_contents:
            if item["name"] == "interpret.py":
                py_file = requests.get(item["url"]).json()
                break
        if not py_file:
            raise Exception("interpret.py not found.")
        progress_var.set(50)

        decoded_code = base64.b64decode(py_file["content"]).decode("utf-8")

        paths_to_try = [
            os.path.expandvars(r"%USERPROFILE%\Scripts"),
            os.path.expandvars(r"%APPDATA%\Python\Scripts"),
            os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Programs", "Python", "Scripts")
        ]

        installed = False
        for path in paths_to_try:
            try:
                os.makedirs(path, exist_ok=True)
                py_path = os.path.join(path, f"{alias_name}.py")
                bat_path = os.path.join(path, f"{alias_name}.bat")
                with open(py_path, "w", encoding="utf-8") as f:
                    f.write(decoded_code)
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(f'@echo off\npython "%~dp0{alias_name}.py" %*\n')
                install_dir = path
                log(debug_output, f"[✓] Installed to: {py_path}")
                log(debug_output, f"[✓] .bat created: {bat_path}")
                installed = True
                break
            except Exception as e:
                log(debug_output, f"[!] Failed to write to {path}: {e}")

        if not installed:
            raise Exception("No writable install folder found.")
        progress_var.set(70)

        # Add to PATH
        current_path = os.environ.get("PATH", "")
        if install_dir.lower() in [p.strip().lower() for p in current_path.split(";")]:
            log(debug_output, "[✓] Install path already in PATH.")
        else:
            try:
                subprocess.run(f'setx PATH "%PATH%;{install_dir}"', shell=True)
                log(debug_output, "[+] PATH updated using setx.")
            except:
                try:
                    subprocess.run([
                        "powershell", "-Command",
                        f'[Environment]::SetEnvironmentVariable("Path", "$env:Path;{install_dir}", "User")'
                    ], shell=True)
                    log(debug_output, "[+] PATH updated using PowerShell.")
                except:
                    log(debug_output, f"[!] Could not add to PATH. Add manually:\n{install_dir}")

        progress_var.set(100)
        log(debug_output, "[✓] Installation complete.")
        messagebox.showinfo("Success", f"Installed as '{alias_name}'. You can now run it from CMD.")
    except Exception as e:
        log(debug_output, f"[✗] Installation failed: {e}")
        messagebox.showerror("Error", f"Installation failed: {e}")
        progress_var.set(0)

# --- Hook button to install ---
next_button.config(command=go_to_install)

# --- Start GUI ---
show_frame(page1)
root.mainloop()
