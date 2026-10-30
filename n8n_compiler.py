"""Compile a small step plan (produced by Gemma) into an n8n workflow JSON."""
import re
import uuid

URL_RE = re.compile(r"https?://[^\s'\"]+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _id(seed):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "ghost-workflow-medium/" + seed))


def _trigger(t, src):
    ttype = (t or {}).get("type", "manual")
    cron = ((t or {}).get("cron") or "").strip()
    if ttype == "schedule":
        return {
            "name": "Schedule (from crontab)",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}},
        }
    if ttype == "webhook":
        return {
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "parameters": {"httpMethod": "POST", "path": re.sub(r"\W+", "-", src).strip("-")},
        }
    return {
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "parameters": {},
    }


def _step(s):
    kind, detail = s.get("kind"), (s.get("detail") or "").strip()
    note = detail
    if kind == "command":
        return "n8n-nodes-base.executeCommand", 1, {"command": detail}, note
    if kind == "http":
        m = URL_RE.search(detail)
        return "n8n-nodes-base.httpRequest", 4.2, {
            "method": "POST" if "post" in detail.lower() else "GET",
            "url": m.group(0) if m else "https://example.com/REPLACE_ME",
        }, note
    if kind == "email":
        m = EMAIL_RE.search(detail)
        return "n8n-nodes-base.emailSend", 2.1, {
            "fromEmail": "robot@example.com",
            "toEmail": m.group(0) if m else "owner@example.com",
            "subject": s.get("name") or "Message from a reincarnated script",
            "emailFormat": "text",
            "text": detail,
        }, note
    if kind == "readFile":
        return "n8n-nodes-base.readWriteFile", 1, {"fileSelector": detail}, note
    if kind == "writeFile":
        return "n8n-nodes-base.readWriteFile", 1, {"operation": "write", "fileName": detail}, note
    # code (and anything unknown) -> a Code node carrying the ghost's intent
    js = "// Ghost's intent: " + detail.replace("\n", " ") + "\n// TODO: port the original logic here.\nreturn $input.all();"
    return "n8n-nodes-base.code", 2, {"jsCode": js}, note


def compile_workflow(plan, source_name="ghost"):
    nodes, used = [], set()

    def add(spec, note=None):
        name = spec["name"][:60] or "Step"
        base, i = name, 2
        while name in used:
            name, i = f"{base} {i}", i + 1
        used.add(name)
        node = {
            "id": _id(source_name + "/" + name),
            "name": name,
            "type": spec["type"],
            "typeVersion": spec["typeVersion"],
            "position": [250 + 220 * len(nodes), 300],
            "parameters": spec["parameters"],
        }
        if note:
            node["notes"] = note
        nodes.append(node)
        return name

    names = [add(_trigger(plan.get("trigger"), source_name))]
    for s in plan.get("steps") or []:
        ntype, ver, params, note = _step(s)
        names.append(add({"name": (s.get("name") or "Step").strip(), "type": ntype,
                          "typeVersion": ver, "parameters": params}, note))
    connections = {
        a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(names, names[1:])
    }
    return {
        "name": (plan.get("workflow_name") or source_name).strip()[:80] + " (reincarnated)",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"generatedBy": "ghost-workflow-medium", "source": source_name},
    }
