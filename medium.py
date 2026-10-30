#!/usr/bin/env python3
"""Ghost Workflow Medium - a local Gemma seance for dead scripts.

Reads an old cron/bash/python script ("the ghost"), asks a local Gemma model
(served by Ollama) to (1) confess what the script did in life, in character,
and (2) describe its job as a small structured plan. The plan is compiled into
an n8n workflow JSON and validated before it is written to reborn/.

Only the Python standard library is used. Nothing leaves your machine.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

from n8n_compiler import compile_workflow
from validate import validate_workflow

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("GHOST_MODEL", "gemma3:1b")

STEP_KINDS = ["command", "http", "email", "code", "readFile", "writeFile"]

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "workflow_name": {"type": "string"},
        "trigger": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["schedule", "webhook", "manual"]},
                "cron": {"type": "string"},
            },
            "required": ["type", "cron"],
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": STEP_KINDS},
                    "name": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["kind", "name", "detail"],
            },
        },
    },
    "required": ["workflow_name", "trigger", "steps"],
}

CONFESS_SYSTEM = (
    "You are the ghost of an old script that ran on a small business server for years. "
    "Speak in the first person, as the ghost. In exactly three short sentences, say what "
    "you did every time you woke up, who depended on you, and what would break if you "
    "were deleted. Be eerie but accurate. Do not invent facts that are not in the script."
)

PLAN_SYSTEM = (
    "You convert old scripts into n8n automation plans. Answer ONLY with JSON. "
    "If the script has a crontab line, trigger is schedule and cron is ONLY the five time "
    "fields (for example '15 2 * * 0'), never the command after them. Each step copies a "
    "real command, URL, path or email address from the script into detail. Never invent a "
    "URL or address that is not in the script. Give each step a short human name. "
    "Do not skip actions: every shell command line is a command step, every curl or HTTP "
    "call is an http step, every mail/smtplib send is an email step, and reading a CSV or "
    "doing arithmetic is a code step.\n\n"
    "Example script:\n"
    "# 15 2 * * 0 /opt/clean.sh\n"
    "rm -rf /tmp/cache/*\n"
    "curl -X POST https://hooks.example.org/done\n"
    "echo cleaned | mail -s 'cache cleaned' ops@example.org\n"
    "Example answer:\n"
    '{"workflow_name": "Weekly cache clean", "trigger": {"type": "schedule", "cron": "15 2 * * 0"}, '
    '"steps": [{"kind": "command", "name": "Clear cache", "detail": "rm -rf /tmp/cache/*"}, '
    '{"kind": "http", "name": "Notify done", "detail": "POST https://hooks.example.org/done"}, '
    '{"kind": "email", "name": "Email ops", "detail": "to ops@example.org subject cache cleaned"}]}'
)

OPTIONS = {"num_predict": 400, "num_thread": int(os.environ.get("GHOST_THREADS", "4"))}


def chat(model, system, user, fmt=None, temperature=0.2, seed=42):
    body = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": dict(OPTIONS, temperature=temperature, seed=seed, num_ctx=4096),
    }
    if fmt is not None:
        body["format"] = fmt
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        resp = json.loads(r.read())
    stats = {
        "wall_s": round(time.time() - t0, 1),
        "prompt_tokens": resp.get("prompt_eval_count"),
        "output_tokens": resp.get("eval_count"),
    }
    return resp["message"]["content"], stats


def cron_hint(script):
    """Find a crontab-looking line in the script, to help a tiny model."""
    m = re.search(r"((?:[\d*/,-]+\s+){4}[\d*/,-]+)\s+\S", script)
    return m.group(1).strip() if m else ""


FIELD = r"[\d*/,\-]+"


def repair_and_ground(plan, script):
    """Deterministic fixes for common small-model mistakes. Returns notes."""
    notes = []
    trig = plan.get("trigger") or {}
    cron = (trig.get("cron") or "").split()
    if trig.get("type") == "schedule" and len(cron) > 5 and all(re.fullmatch(FIELD, c) for c in cron[:5]):
        trig["cron"] = " ".join(cron[:5])
        notes.append(f"\U0001F527 trimmed cron to '{trig['cron']}' (model copied the command too)")
    kept = []
    for st in plan.get("steps") or []:
        found = re.findall(r"https?://[^\s'\"]+|[\w.+-]+@[\w-]+\.[\w.]+", st.get("detail", ""))
        lies = [x.rstrip(".,)") for x in found if x.rstrip(".,)") not in script]
        if lies:
            notes.append(f"\U0001F9FF exorcised step '{st.get('name')}': {lies[0]} is not in the original script")
            continue
        if st.get("kind") == "http" and not re.search(r"https?://", st.get("detail", "")):
            st["kind"] = "command"
            notes.append(f"\U0001F527 re-typed step '{st.get('name')}' as a shell command (no URL in it)")
        kept.append(st)
    plan["steps"] = kept
    return notes


def summon(path, model, outdir, max_retries=1):
    name = os.path.splitext(os.path.basename(path))[0]
    script = open(path, encoding="utf-8").read()
    print(f"\U0001F56F  Summoning the ghost of {os.path.basename(path)} with {model} ...")

    story, s1 = chat(model, CONFESS_SYSTEM, script, temperature=0.7)
    story = " ".join(story.split())
    print(f"\U0001F47B {story}")
    print(f"   (confession: {s1['output_tokens']} tokens, {s1['wall_s']}s)")

    hint = cron_hint(script)
    user = script + (f"\n\n# Hint: the cron expression in this script is: {hint}" if hint else "")
    feedback = ""
    for attempt in range(max_retries + 1):
        raw, s2 = chat(model, PLAN_SYSTEM, user + feedback, fmt=PLAN_SCHEMA)
        print(f"   (plan attempt {attempt + 1}: {s2['output_tokens']} tokens, {s2['wall_s']}s)")
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError as e:
            errors = [f"plan is not valid JSON: {e}"]
            plan = None
        if plan is not None:
            for n in repair_and_ground(plan, script):
                print("   " + n)
            wf = compile_workflow(plan, source_name=os.path.basename(path))
            errors = validate_workflow(wf)
        if not errors:
            break
        print("   \u26A0 validation failed: " + "; ".join(errors))
        feedback = "\n\n# Your previous answer was rejected: " + "; ".join(errors) + ". Fix it."

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, name + ".story.txt"), "w", encoding="utf-8") as f:
        f.write(story + "\n")
    if plan is not None:
        with open(os.path.join(outdir, name + ".plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
    if errors:
        print(f"\u274C Could not reincarnate {name}: " + "; ".join(errors))
        return False
    out = os.path.join(outdir, name + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    kinds = " -> ".join(n["type"].split(".")[-1] for n in wf["nodes"])
    print(f"\u2728 Reincarnated -> {out} ({len(wf['nodes'])} nodes: {kinds}); structure check passed")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ghosts", nargs="+", help="old script files to summon")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default="reborn")
    ap.add_argument("--retries", type=int, default=1)
    a = ap.parse_args()
    ok = sum(summon(p, a.model, a.out, a.retries) for p in a.ghosts)
    print(f"\n{ok}/{len(a.ghosts)} ghosts reincarnated.")
    sys.exit(0 if ok == len(a.ghosts) else 1)


if __name__ == "__main__":
    main()
