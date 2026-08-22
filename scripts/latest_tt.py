"""Print the most recent TimeTrial.GetLeaderboardId capture: filename + TrackModelId.

Usage: latest_tt.py [wait_seconds] [after_filename]
With wait_seconds, polls (1s) until a capture newer than after_filename appears.
"""
import json, os, sys, time

CAPDIR = "C:/Users/winrid/dr2server/captures"


def latest():
    for fn in sorted(os.listdir(CAPDIR), reverse=True)[:60]:
        p = os.path.join(CAPDIR, fn)
        if not fn.endswith(".json"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        if d.get("headers", {}).get("X-EgoNet-Function") != "TimeTrial.GetLeaderboardId":
            continue
        body = d.get("decoded_body", {}) or {}
        def v(x):
            return x.get("value", x) if isinstance(x, dict) else x
        return fn, v(body.get("TrackModelId")), v(body.get("VehicleClassId")), v(body.get("ConditionsId"))
    return None, None, None, None


wait = int(sys.argv[1]) if len(sys.argv) > 1 else 0
after = sys.argv[2] if len(sys.argv) > 2 else None
deadline = time.time() + wait
while True:
    fn, tm, vc, cond = latest()
    if fn and fn != after:
        print(f"{fn} track={tm} vclass={vc} cond={cond}")
        break
    if time.time() >= deadline:
        print(f"{fn or '-'} track={tm} (no new capture)")
        break
    time.sleep(1)
