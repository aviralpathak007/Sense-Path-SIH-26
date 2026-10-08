"""Build the demo scenario + road network from a HELD-OUT IO-VNBD run.

Window rule (fixed, not outcome-based): the first 6-minute stretch of the held-out run in which at least
95% of samples are above 3 m/s. A 90 s GNSS outage is cut starting 3 minutes in. Roads come from
OpenStreetMap via the Overpass API (public data) and are saved as an offline GeoJSON asset.

    venv/bin/python scripts/make_scenario.py [A_S1]
"""
import json
import os
import sys
import urllib.parse
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ml_pipeline"))
from runs import load_run  # noqa: E402

RUN = sys.argv[1] if len(sys.argv) > 1 else "A_S1"
WIN, OUT_START, OUT_LEN = 3600, 1800, 900   # samples at 10 Hz: 6 min window, outage 3:00 -> 4:30


def pick_window(r):
    v = r["gt_speed"]
    ok = (v > 3.0).astype(int)
    for s in range(2000, len(v) - WIN, 50):
        if ok[s:s + WIN].mean() >= 0.95 and not np.isnan(r["gt_lat"][s:s + WIN]).any():
            return s
    raise SystemExit("no continuous-driving window found")


def overpass(south, west, north, east):
    q = (f'[out:json][timeout:60];way["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|'
         f'residential|living_street|service|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"]'
         f'({south},{west},{north},{east});out geom;')
    last = None
    for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
                "https://lz4.overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"):
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": "sense-path-sih/1.0"})
            with urllib.request.urlopen(req, timeout=120) as f:
                return json.load(f)
        except Exception as e:  # noqa: BLE001
            last = e
            print("overpass mirror failed:", url, e)
    raise SystemExit(f"all Overpass mirrors failed: {last}")


def main():
    r = load_run(RUN)
    s = pick_window(r)
    sl = slice(s, s + WIN)
    lat, lon, hd, sp = r["gt_lat"][sl], r["gt_lon"][sl], r["gt_heading"][sl], r["gt_speed"][sl]
    dist = float(np.sum(sp[OUT_START:OUT_START + OUT_LEN]) * 0.1)
    frames = []
    for i in range(WIN):
        denied = OUT_START <= i < OUT_START + OUT_LEN
        frames.append([round(float(x), 4) for x in (*r["acc"][s + i], *r["gyro"][s + i])]
                      + [round(float(lat[i]), 7), round(float(lon[i]), 7), round(float(hd[i]), 2), round(float(sp[i]), 3), int(denied)])
    meta = {"name": f"{RUN} held-out window", "run": RUN, "source_start_sample": int(s), "rate_hz": 10,
            "outage_start_frame": OUT_START, "outage_frames": OUT_LEN, "outage_distance_m": round(dist, 1),
            "columns": ["ax", "ay", "az", "gx", "gy", "gz", "lat", "lon", "bearing", "speed", "gnss_denied"],
            "note": "acc/gyro: raw phone IMU incl. gravity; lat/lon/bearing/speed: vehicle reference logger used as GNSS"}
    out = os.path.join(ROOT, "assets", "scenarios", "heldout_outage_scenario.json")
    json.dump({"meta": meta, "frames": frames}, open(out, "w"), separators=(",", ":"))
    print("scenario:", out, os.path.getsize(out) // 1024, "KB; outage distance", meta["outage_distance_m"], "m")

    np.savez_compressed(os.path.join(ROOT, "edge_engine", "replay", "heldout_segment.npz"),
                        acc=r["acc"][sl], gyro=r["gyro"][sl], lat=lat, lon=lon, bearing=hd, speed=sp,
                        outage=np.array([OUT_START, OUT_START + OUT_LEN]))

    pad = 0.004
    data = overpass(lat.min() - pad, lon.min() - pad, lat.max() + pad, lon.max() + pad)
    feats = []
    for w in data.get("elements", []):
        if w.get("type") == "way" and w.get("geometry"):
            feats.append({"type": "Feature", "properties": {"name": w.get("tags", {}).get("name", ""), "highway": w["tags"].get("highway", "")},
                          "geometry": {"type": "LineString", "coordinates": [[round(p["lon"], 6), round(p["lat"], 6)] for p in w["geometry"]]}})
    rp = os.path.join(ROOT, "assets", "maps", "road_network.json")
    json.dump({"type": "FeatureCollection", "features": feats}, open(rp, "w"), separators=(",", ":"))
    print("roads:", len(feats), "ways ->", rp, os.path.getsize(rp) // 1024, "KB")


if __name__ == "__main__":
    main()
