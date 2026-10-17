"""0.18.11 model-selected Groovy method-scope evidence; no hardcoded app logic."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))

from groovy_method_scope import build_method_scope_evidence
from groovy_source_investigation import GroovySourceService


def test_brace_lexing_ignores_comments_strings_and_closure_braces():
    source = (
        "private int getDuration() {\n"
        "  // fake close }\n"
        "  String s = 'brace } as text'\n"
        "  /* { ignored } */\n"
        "  def state = [:]\n"
        "  if (state) { return 300 }\n"
        "  return 3\n"
        "}\n"
        "void updated() { initialize() }\n"
    )
    notes, excerpts = build_method_scope_evidence(
        source, ("getDuration", "updated()"), budget=12000
    )
    assert len(excerpts) == 2
    assert "return 3" in excerpts[0]
    assert "void updated()" in excerpts[1]
    assert any("getDuration lines 1-8" in item and
               "full candidate method body shown" in item for item in notes)
    assert any("updated lines 9-9" in item and
               "full candidate method body shown" in item for item in notes)


def test_field_symbol_collects_read_write_owners_without_inferring_behavior():
    source = (
        "void startCountdown() {\n"
        "  state.lockout = now() + 180000\n"
        "}\n"
        "boolean isLocked() {\n"
        "  return state.lockout > now()\n"
        "}\n"
        "void updated() {\n"
        "  /* existing expiry is not rewritten here */\n"
        "  state.configVersion = 2\n"
        "}\n"
    )
    notes, excerpts = build_method_scope_evidence(
        source, ("state.lockout", "updated()", "isLocked"), budget=12000
    )
    joined="\n".join(excerpts)
    assert "state.lockout = now()" in joined
    assert "return state.lockout > now()" in joined
    assert "state.configVersion = 2" in joined
    assert "startCountdown lines 1-3" in "\n".join(notes)
    assert "isLocked lines 4-6" in "\n".join(notes)
    assert "complete call graph" in "\n".join(notes)


def test_large_method_explicitly_unseen_even_if_complete_source_available():
    source = (
        "void updated() {\n"
        + "\n".join("    state.longTerm = 4" for _ in range(300))
        + "\n}\n"
        "void initialize() {\n  state.safe = true\n}\n"
    )
    notes, excerpts = build_method_scope_evidence(
        source, ("updated()", "initialize()"), budget=900
    )
    joined_notes="\n".join(notes)
    assert "updated" in joined_notes
    assert "complete method body NOT shown" in joined_notes
    assert "void initialize()" in "\n".join(excerpts)
    assert "full candidate method body shown" in joined_notes


def test_unbalanced_method_and_slashy_regex_never_claim_balanced_body():
    unknown=(
        "void updated() {\n"
        "  def pattern = /a{1,3}/\n"
        "  state.duration = 3\n"
        "}\n"
        "void initialize() {\n"
    )
    notes, excerpts=build_method_scope_evidence(
        unknown, ("updated()", "initialize()"), budget=4000
    )
    assert excerpts
    lines="\n".join(notes)
    assert "boundary uncertain" in lines
    assert "updated" in lines
    assert "initialize" in lines
    assert "endpoint NOT verified" in lines


def test_unknown_name_not_promoted_to_absent_method():
    notes, excerpts=build_method_scope_evidence(
        "void boot() {\n state.x = 2\n}\n",
        ("randomFunction",), budget=1000
    )
    assert excerpts == []
    assert "no recognized enclosing method" in "\n".join(notes)
    assert "not a Groovy compiler" in "\n".join(notes)


class Audit:
    def __init__(self):
        self.rows=[]
    def record(self, gateway, args, **meta):
        self.rows.append((gateway,args,meta))


class CompleteSourceMCP:
    def __init__(self):
        self.code=(
            "void updated() {\n"
            "  def outer = [one: 1]\n"
            "  if (outer) {\n"
            "    state.lockoutExpiry = 12345\n"
            "  }\n"
            "  return\n"
            "}\n"
            "boolean isDeviceLocked() {\n"
            "  return state.lockoutExpiry > now()\n"
            "}\n"
        )
        self.code = self.code + ("// Groovy source padding\n" * 8000)
        self.code = self.code[:186457]
        self.calls=[]
    async def list_tools(self):
        return [
            SimpleNamespace(name="hub_search_tools",input_schema={}),
            SimpleNamespace(
                name="hub_read_apps_code",
                input_schema={"properties":{"tool":{"enum":[
                    "hub_get_source","hub_get_app_config","hub_list_apps"
                ]}}},
            ),
        ]
    async def call_tool(self,name,args):
        self.calls.append((name,args))
        if name=="hub_search_tools":
            data={"results":[{"gateway":"hub_read_apps_code",
                              "tool":"hub_get_source"}]}
        elif args["tool"]=="hub_get_app_config":
            data={"app":{"id":"4019","appTypeId":"1453"}}
        elif args["tool"]=="hub_get_source":
            p=args["args"]
            chunk=self.code[p["offset"]:p["offset"]+p["length"]]
            data={"source":chunk, "appId":1453, "offset":p["offset"],
                  "nextOffset":p["offset"]+len(chunk),
                  "totalLength":len(self.code),
                  "version":96,
                  "hasMore":p["offset"]+len(chunk)<len(self.code)}
        else:
            raise AssertionError(args)
        return SimpleNamespace(data=data,is_error=False)


def test_complete_source_does_not_conflate_file_with_method_evidence():
    async def run():
        mcp=CompleteSourceMCP()
        assert len(mcp.code)==186457
        result=await GroovySourceService(mcp,Audit()).inspect(
            "4019", symbols=[
                "state.lockoutExpiry","updated()","isDeviceLocked()"
            ],
        )
        assert result.complete
        assert result.verified_characters==186457
        assert result.source_code_id=="1453"
        assert "Method-scope evidence" in result.message
        assert "full candidate method body shown" in result.message
        assert "state.lockoutExpiry = 12345" in result.message
        assert "return state.lockoutExpiry > now()" in result.message
        assert "not a Groovy compiler" in result.message
        assert len([1 for _,a in mcp.calls
                    if a.get("tool")=="hub_get_source"])==4
    asyncio.run(run())
