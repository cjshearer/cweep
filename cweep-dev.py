import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from ocp_vscode.standalone import Viewer
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

viewer = Viewer({"port": 3939, "host": "127.0.0.1"})
viewer_thread = threading.Thread(target=viewer.start, daemon=True)
viewer_thread.start()
webbrowser.open("http://127.0.0.1:3939")

cwd = Path(__file__).parent
script = cwd / "cweep.py"
pcb_file = cwd / "cweep.kicad_pcb"
step_file = cwd / "case" / "cweep.step"
sys.argv = [script, "--preview"]
ctx = {"__file__": str(script)}

# We generate a model of the PCB if we can, which is helpful for validating case fitment during
# development
if shutil.which("kicad-cli") and not (
    step_file.exists() and step_file.stat().st_mtime > pcb_file.stat().st_mtime
):
    subprocess.run(
        [
            "kicad-cli",
            "pcb",
            "export",
            "step",
            "--force",
            "--fuse-shapes",
            # Although including this soldermask would make the percieved thickness of the board
            # more accurate, the thin faces kicad exports for the silkscreen make the viewer bug out
            # when clipping the model, so I don't actually incldue them except for validating that
            # the placement of the models is correct
            # "--include-soldermask",
            "--subst-models",
            "--output",
            str(step_file),
            str(pcb_file),
        ]
    )


class H(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = {}

    def on_modified(self, event):
        if event is not None and event.src_path not in (str(script), str(pcb_file)):
            return
        watched_file = event.src_path if event else str(script)
        current_mtime = os.path.getmtime(watched_file)
        if self.last_modified.get(watched_file) == current_mtime:
            return
        self.last_modified[watched_file] = current_mtime
        print("\033[2J\033[H")  # Clear terminal
        filename = Path(watched_file).name if event else "cweep.py"
        print(f"{filename} modified, reloading...")
        try:
            exec(open(script).read(), ctx)
        except Exception as e:
            sys.excepthook(type(e), e, e.__traceback__)


h = H()
obs = Observer()
obs.schedule(h, str(cwd), recursive=False)
obs.start()

print("watching cweep.py")
h.on_modified(None)

try:
    obs.join()
except KeyboardInterrupt:
    print("\nShutting down...")
    obs.stop()
    obs.join()
