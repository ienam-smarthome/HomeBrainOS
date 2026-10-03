from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Explicit internet/access wording must win before the bare-unblock fallback.
p = ROOT / 'hubitat-mcp-ai/rootfs/app/request_classification.py'
text = p.read_text(encoding='utf-8')
old = '''        (_BLOCK_INTERNET, "blockInternet"),
        (_ALLOW_INTERNET, "allowInternet"),
        (_UNBLOCK_INTERNET, "allowInternet"),
        (_ALLOW_INTERNET_EXPLICIT, "allowInternet"),
'''
new = '''        (_BLOCK_INTERNET, "blockInternet"),
        (_ALLOW_INTERNET, "allowInternet"),
        (_ALLOW_INTERNET_EXPLICIT, "allowInternet"),
        (_UNBLOCK_INTERNET, "allowInternet"),
'''
if old not in text:
    raise SystemExit('parser ordering marker missing')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Update the old parser-level safety contract: bare restore remains excluded;
# bare unblock is admitted, but execution safety now lives at the authoritative
# Internet-room boundary and must fail closed there.
p = ROOT / 'tests/test_internet_access_hardening.py'
t = p.read_text(encoding='utf-8')
old_block = '''def test_immediate_parser_recognises_restrict_and_explicit_unblock_restore():
    """Hardening pass addition: "restrict" is an unambiguous internet-access
    synonym for "block" and is safe to accept the same way "disable"
    already is. "unblock"/"restore" are NOT safe to accept as loosely --
    both words are heavily overloaded elsewhere (a hub backup can be
    "restored") -- so they only count as internet-access requests when
    "internet"/"access" is stated explicitly.
    """
'''
new_block = '''def test_immediate_parser_recognises_restrict_and_explicit_unblock_restore():
    """Restrict remains a block synonym; explicit unblock/restore wording
    must strip its internet/access clause before returning the target.

    Bare `unblock <target>` is covered separately because 0.16.99 moves its
    safety boundary to authoritative Internet-room resolution. Bare `restore`
    remains excluded because restore is overloaded with backups/defaults.
    """
'''
if old_block not in t:
    raise SystemExit('hardening doc marker missing')
t = t.replace(old_block, new_block, 1)
old_test = '''def test_bare_unblock_or_restore_without_internet_wording_is_never_hijacked():
    """The exact failure mode the stricter explicit-clause requirement
    exists to prevent: "restore the backup" (a real, unrelated hub
    operation) must never be reinterpreted as "unblock a device named
    backup" just because "restore" is also a valid internet-access verb
    when paired with explicit "internet"/"access" wording.
    """

    assert parse_immediate_internet_access_intent("restore the backup") is None
    assert parse_immediate_internet_access_intent("restore default settings") is None
    assert parse_immediate_internet_access_intent("unblock the front door") is None
'''
new_test = '''def test_bare_restore_stays_explicit_while_bare_unblock_enters_room_scoped_path():
    """`restore` remains explicit-only because it is overloaded with backup
    and settings operations. Bare `unblock`, however, may enter the immediate
    Internet path because 0.16.99 then scopes execution to the authoritative
    Internet room and fails closed for ordinary devices outside that room.
    """

    assert parse_immediate_internet_access_intent("restore the backup") is None
    assert parse_immediate_internet_access_intent("restore default settings") is None
    assert parse_immediate_internet_access_intent("unblock the front door") == (
        "front door", "allowInternet",
    )
'''
if old_test not in t:
    raise SystemExit('bare unblock hardening test marker missing')
t = t.replace(old_test, new_test, 1)
p.write_text(t, encoding='utf-8')

# Pin the downstream safety boundary too: a bare unblock of an ordinary target
# that is not in Internet must not send any device command.
p = ROOT / 'tests/test_homebrain_agent.py'
t = p.read_text(encoding='utf-8')
anchor = '''@pytest.mark.asyncio
async def test_unconverged_block_reports_uncertainty_not_silent_success() -> None:
'''
extra = '''@pytest.mark.asyncio
async def test_bare_unblock_non_internet_target_fails_closed_without_command() -> None:
    mcp = InternetAccessMCP(converged=True)
    agent = UnifiedMCPAgent(mcp, "key", ai_client=FakeAI("unused"))

    outcome = await agent.process_user_request_result(
        "unblock the front door", session_id="unblock-front-door-safety"
    )

    assert "authoritative **Internet** group" in outcome.message
    dispatch_calls = [
        args for _, args in mcp.calls if args.get("tool") == "hub_call_device_command"
    ]
    assert dispatch_calls == []


'''
if extra not in t:
    if anchor not in t:
        raise SystemExit('homebrain test insertion marker missing')
    t = t.replace(anchor, extra + anchor, 1)
p.write_text(t, encoding='utf-8')

for rel in ['.github/scripts/fix_0_16_99_ci.py', '.github/workflows/fix_0_16_99_ci.yml']:
    q = ROOT / rel
    if q.exists():
        q.unlink()
