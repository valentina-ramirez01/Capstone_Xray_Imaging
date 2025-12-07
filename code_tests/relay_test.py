# relay_test.py
import sys
from pathlib import Path
import time

_here = Path(__file__).resolve()

# walk upward until we find the folder containing "xavier"
project_root = None
for parent in [_here.parent, *_here.parents]:
    if (parent / "xavier").is_dir():
        project_root = parent
        break

if project_root is None:
    raise RuntimeError("Could not find the 'xavier' folder.")

# Add project root to sys.path
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# --------------------------------------------------------
# NOW IMPORT WORKS
# --------------------------------------------------------
from xavier.relay import hv_on, hv_off

print("Relay Test")
print("Type 's' to activate relay for 3 seconds.")
print("Type 'q' to quit.\n")

while True:
    cmd = input("> ").strip().lower()

    if cmd == "q":
        print("Exiting...")
        break

    if cmd == "s":
        print("Relay ON")
        hv_on()
        time.sleep(3)
        hv_off()
        print("Relay OFF")
    else:
        print("Unknown command. Use 's' or 'q'.")