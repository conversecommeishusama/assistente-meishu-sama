import json
import subprocess
import sys

args = json.load(open("/tmp/mescla103_args.json", encoding="utf-8"))
if "--aplicar" in sys.argv:
    args = args + ["--aplicar"]
subprocess.run(args, check=False)
