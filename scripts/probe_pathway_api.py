"""
Pathway 0.29.1 API Probe Script.
Run: docker cp to container, then python /tmp/probe_api.py
"""
import pathway as pw
import sys

print(f"Pathway version: {pw.__version__}")
print()

# --- pw.io.python ---
print("=== pw.io.python ===")
import inspect
try:
    import pathway.io.python as pyio
    print("Members:", [m for m in dir(pyio) if not m.startswith("_")])
except Exception as e:
    print("Error:", e)

# ConnectorSubject
try:
    subj = pw.io.python.ConnectorSubject()
    print("ConnectorSubject methods:", [m for m in dir(subj) if not m.startswith("_")])
except Exception as e:
    print("ConnectorSubject error:", e)

print()
# --- pw.temporal ---
print("=== pw.temporal ===")
try:
    import pathway.stdlib.temporal as temporal
    print("temporal members:", [m for m in dir(temporal) if not m.startswith("_")])
except Exception as e:
    print("temporal import error:", e)

try:
    import pathway.temporal as t2
    print("pathway.temporal members:", [m for m in dir(t2) if not m.startswith("_")])
except Exception as e:
    print("pathway.temporal error:", e)

print()
# --- pw.reducers ---
print("=== pw.reducers ===")
try:
    print("reducers members:", [m for m in dir(pw.reducers) if not m.startswith("_")])
except Exception as e:
    print("reducers error:", e)

print()
# --- pw.run ---
print("=== pw.run signature ===")
try:
    print(inspect.signature(pw.run))
except Exception as e:
    print("run error:", e)

print()
# --- windowby ---
print("=== windowby check ===")
try:
    # Try to find windowby
    schema = pw.schema_from_dict({"val": float, "t": pw.DateTimeUtc})
    t_table = pw.Table.empty(**{f: pw.column_definition() for f in ["val"]})
    print("Table methods with 'window':", [m for m in dir(pw.Table) if "window" in m.lower()])
except Exception as e:
    print("windowby check error:", e)
