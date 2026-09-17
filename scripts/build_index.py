#!/usr/bin/env python3
"""Merge mods/*.json into index.json (sorted by name)."""
import glob, json

entries = sorted((json.load(open(p)) for p in glob.glob("mods/*.json")), key=lambda e: e["name"])
json.dump({"mods": entries}, open("index.json", "w"), indent=2)
open("index.json", "a").write("\n")
print(f"{len(entries)} mods")
