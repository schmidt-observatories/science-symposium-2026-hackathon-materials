"""Run the Python reference engine on tests/cases.json and store the outputs for the JS parity test."""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
from dsa_etc import DSACalculator, rfi_none, rfi_measured
import numpy as np

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o); return v if math.isfinite(v) else ("inf" if v > 0 else "-inf")
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.bool_): return bool(o)
    return o

cases = json.load(open(os.path.join(HERE, "cases.json")))
out = []
for c in cases:
    rfi = {"none": rfi_none, "measured": rfi_measured}.get(c.get("rfi"), lambda: None)()
    calc = DSACalculator(rfi=rfi, **c.get("params", {}))
    r = calc.calculate(**c["inp"])
    out.append({"name": c["name"], "result": clean(r)})
json.dump(out, open(os.path.join(HERE, "reference_outputs.json"), "w"))
print("wrote", len(out), "reference cases")
