import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ver1.2"))

from ruby import runRuby, StableHash

lines = []
while True:
    line = input(">>> ")
    if line == "run":
        runRuby("".join(lines))
        lines.clear()
        continue
    lines.append(line + "\n")