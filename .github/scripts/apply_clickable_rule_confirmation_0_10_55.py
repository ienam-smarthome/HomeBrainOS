from pathlib import Path

root = Path(__file__).resolve().parents[2]
controller = root / "hubitat-mcp-ai/rootfs/app/named_rule_control.py"
text = controller.read_text(encoding="utf-8")
old = '''        return {
            "success": False,
            "route": "mcp-rule-clarification",
            "intent": "automation-rule-clarification",
            "message": message,
            "display": display_payload(
                "rules",
                "Confirm rule",
                subtitle="No command has been sent",
                items=[
                    {
                        "icon": "⚙️",
                        "title": rule["name"],
                        "value": str(rule["id"]),
                        "subtitle": "Reply with the exact name or Rule ID",
                    }
                    for rule in candidates
                ],
            ),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested": intent.requested_name, "candidates": candidates, "mcp": listed.data}),
        }
'''
new = '''        display = display_payload(
            "rules",
            "Confirm rule",
            subtitle="No command has been sent",
            items=[
                {
                    "icon": "⚙️",
                    "title": rule["name"],
                    "value": str(rule["id"]),
                    "subtitle": "Select this rule or cancel",
                }
                for rule in candidates
            ],
        )
        if candidates:
            if len(candidates) == 1:
                action_label = f"Confirm {intent.action}"
                action_rules = candidates
            else:
                action_label = ""
                action_rules = candidates[:5]
            display["actions"] = [
                {
                    "label": action_label or f"{intent.action.title()} {rule['name']}",
                    "query": f"{intent.action} rule id {rule['id']}",
                    "tone": "primary",
                }
                for rule in action_rules
            ] + [{"label": "Cancel", "cancel": True, "tone": "secondary"}]

        return {
            "success": False,
            "route": "mcp-rule-clarification",
            "intent": "automation-rule-clarification",
            "message": message,
            "display": display,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "technical": safe_debug({"requested": intent.requested_name, "candidates": candidates, "mcp": listed.data}),
        }
'''
if old not in text:
    raise SystemExit("clarification response block not found")
controller.write_text(text.replace(old, new, 1), encoding="utf-8")

ui = root / "hubitat-mcp-ai/rootfs/app/webui_homebrain.py"
text = ui.read_text(encoding="utf-8")
old = "if(answer.display.note)output.appendChild(el('div','mini',answer.display.note));if(answer.message&&!answer.display.metrics?.length&&!answer.display.items?.length)output.appendChild(el('div','answer-text',answer.message))"
new = "if(answer.display.note)output.appendChild(el('div','mini',answer.display.note));if(Array.isArray(answer.display.actions)&&answer.display.actions.length){const actionBar=el('div','answer-actions');answer.display.actions.forEach(action=>{const button=el('button','small-button '+(action.tone==='primary'?'confirm-action':''),action.label||'Select');button.onclick=()=>{if(action.cancel){clearOutput();output.appendChild(el('div','answer-text','Cancelled. No command was sent.'));return}if(action.query){input.value=action.query;submit(action.query)}};actionBar.appendChild(button)});output.appendChild(actionBar)}if(answer.message&&!answer.display.metrics?.length&&!answer.display.items?.length)output.appendChild(el('div','answer-text',answer.message))"
if old not in text:
    raise SystemExit("web UI display action marker not found")
text = text.replace(old, new, 1)
text = text.replace(
    ".small-button{width:auto;margin:0;padding:7px 10px;background:#333;font-size:12px}",
    ".small-button{width:auto;margin:0;padding:7px 10px;background:#333;font-size:12px}.small-button.confirm-action{background:#166534}",
)
ui.write_text(text, encoding="utf-8")

test = root / "tests/test_hubitat_mcp_ai_named_rule_control.py"
text = test.read_text(encoding="utf-8")
addition = '''

def test_single_partial_rule_match_exposes_clickable_confirm_and_cancel_actions():
    client = FakeMCP()
    answer = ask(application(client), "pause fridge door rule")
    assert answer["success"] is False
    assert answer["route"] == "mcp-rule-clarification"
    assert [name for name, _ in client.calls] == ["hub_list_rules"]
    assert answer["display"]["actions"] == [
        {"label": "Confirm pause", "query": "pause rule id 2967", "tone": "primary"},
        {"label": "Cancel", "cancel": True, "tone": "secondary"},
    ]


def test_confirm_query_uses_exact_rule_id_and_executes_existing_safe_path():
    client = FakeMCP()
    app = application(client)
    clarification = ask(app, "pause fridge door rule")
    answer = ask(app, clarification["display"]["actions"][0]["query"])
    assert answer["success"] is True
    assert client.calls[-1] == ("hub_set_rule_paused", {"ruleId": 2967, "paused": True})
'''
if "test_single_partial_rule_match_exposes_clickable_confirm" not in text:
    test.write_text(text.rstrip() + addition + "\n", encoding="utf-8")

def replace(path: Path, old: str, new: str) -> None:
    data = path.read_text(encoding="utf-8")
    if old not in data:
        raise SystemExit(f"missing release marker in {path}: {old}")
    path.write_text(data.replace(old, new), encoding="utf-8")

replace(root / "hubitat-mcp-ai/config.yaml", 'version: "0.10.54"', 'version: "0.10.55"')
replace(root / "hubitat-mcp-ai/rootfs/app/entrypoint.py", 'PREVIOUS_RELEASE_VERSION = "0.10.53"\nRELEASE_VERSION = "0.10.54"', 'PREVIOUS_RELEASE_VERSION = "0.10.54"\nRELEASE_VERSION = "0.10.55"')
replace(root / "hubitat-mcp-ai/rootfs/app/device_intelligence_webui.py", 'PWA_RELEASE_VERSION = "0.10.54"', 'PWA_RELEASE_VERSION = "0.10.55"')
replace(root / "hubitat-mcp-ai/README.md", "Current add-on version: **0.10.54**", "Current add-on version: **0.10.55**")
replace(root / "scripts/setup-homebrain-ollama-cloud.ps1", "Update and restart Hubitat MCP AI 0.10.54.", "Update and restart Hubitat MCP AI 0.10.55.")

changelog = root / "hubitat-mcp-ai/CHANGELOG.md"
data = changelog.read_text(encoding="utf-8")
section = """## 0.10.55

- Adds clickable Confirm and Cancel controls when a named rule command has one likely match.
- Shows selectable rule actions when several candidates are returned.
- Confirmation resubmits the exact Rule ID through the existing deterministic safety path.

"""
if "## 0.10.55" not in data:
    changelog.write_text(data.replace("# Hubitat MCP AI changelog\n\n", "# Hubitat MCP AI changelog\n\n" + section, 1), encoding="utf-8")
(root / "hubitat-mcp-ai/CHANGELOG-0.10.55.md").write_text(
    "# Hubitat MCP AI 0.10.55\n\n- Adds clickable rule confirmation and cancellation controls.\n- Uses exact Rule IDs for confirmed actions.\n- Supports candidate selection when more than one likely rule is found.\n",
    encoding="utf-8",
)
