import sys
sys.path.insert(0, r"../../ver1.2")

from ruby import runRuby, StableHash

lines = []
while True:
    line = input(">>> ")
    if line == "run":
        runRuby("".join(lines))
        lines.clear()
        continue
    lines.append(line + "\n")