#!/usr/bin/env python3
"""Structural validator for n8n workflow JSON (no n8n install needed).

Usage: python validate.py reborn/*.json
"""
import json
import re
import sys

KNOWN_TYPES = {
    "n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.webhook", "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.executeCommand", "n8n-nodes-base.httpRequest", "n8n-nodes-base.emailSend",
    "n8n-nodes-base.code", "n8n-nodes-base.readWriteFile",
}
TRIGGERS = {"n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.webhook", "n8n-nodes-base.manualTrigger"}
CRON_FIELD = r"[\d*/,\-]+"
CRON_RE = re.compile(rf"^{CRON_FIELD}(\s+{CRON_FIELD}){{4}}$")


def validate_workflow(wf):
    errs = []
    if not isinstance(wf, dict):
        return ["workflow is not an object"]
    if not isinstance(wf.get("name"), str) or not wf["name"].strip():
        errs.append("missing workflow name")
    nodes = wf.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return errs + ["'nodes' must be a non-empty list"]
    conns = wf.get("connections")
    if not isinstance(conns, dict):
        return errs + ["'connections' must be an object"]
    names = [n.get("name") for n in nodes]
    if len(set(names)) != len(names):
        errs.append("node names are not unique")
    for n in nodes:
        for k in ("id", "name", "type", "typeVersion", "position", "parameters"):
            if k not in n:
                errs.append(f"node {n.get('name')!r} missing '{k}'")
        if n.get("type") not in KNOWN_TYPES:
            errs.append(f"node {n.get('name')!r} has unknown type {n.get('type')!r}")
        pos = n.get("position")
        if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, (int, float)) for v in pos)):
            errs.append(f"node {n.get('name')!r} has bad position")
        if n.get("type") == "n8n-nodes-base.scheduleTrigger":
            for iv in n["parameters"].get("rule", {}).get("interval", []):
                expr = iv.get("expression", "")
                if iv.get("field") == "cronExpression" and not CRON_RE.match(expr.strip()):
                    errs.append(f"invalid cron expression {expr!r}")
        if n.get("type") == "n8n-nodes-base.executeCommand" and not n["parameters"].get("command", "").strip():
            errs.append(f"node {n.get('name')!r} has an empty command")
    triggers = [n["name"] for n in nodes if n.get("type") in TRIGGERS]
    if len(nodes) - len(triggers) < 1:
        errs.append("workflow has no action steps after the trigger")
    if len(triggers) != 1:
        errs.append(f"expected exactly 1 trigger, found {len(triggers)}")
    nameset = set(names)
    for src, outs in conns.items():
        if src not in nameset:
            errs.append(f"connection from unknown node {src!r}")
        for branch in outs.get("main", []):
            for c in branch:
                if c.get("node") not in nameset:
                    errs.append(f"connection to unknown node {c.get('node')!r}")
    if len(triggers) == 1:  # every node must be reachable from the trigger
        seen, todo = set(), [triggers[0]]
        while todo:
            cur = todo.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for branch in conns.get(cur, {}).get("main", []):
                todo += [c["node"] for c in branch]
        orphans = nameset - seen
        if orphans:
            errs.append(f"unreachable nodes: {sorted(orphans)}")
    return errs


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        e = validate_workflow(json.load(open(p)))
        print(("OK   " if not e else "FAIL ") + p + ("" if not e else ": " + "; ".join(e)))
        bad += bool(e)
    sys.exit(1 if bad else 0)
