"""V2 answer display uses safe DOM nodes; native answers/receipts stay unchanged."""
from pathlib import Path
import shutil
import subprocess
import unittest

UI = Path(__file__).resolve().parents[1] / "rootfs" / "app" / "ui.html"


class ReadableAnswerRenderingTests(unittest.TestCase):
    def test_safe_legacy_br_renderer_and_narrow_tables(self):
        html = UI.read_text(encoding="utf-8")
        self.assertIn("function appendInlineSegment(node,text)", html)
        self.assertIn("String(text).split(/<br", html)
        self.assertIn("document.createElement('br')", html)
        self.assertIn("table.setAttribute('data-columns',String(cells.length))", html)
        self.assertIn("table[data-columns=\"2\"] th:first-child", html)
        self.assertIn("byId('rawAnswer').textContent=answer", html)
        self.assertIn("byId('answer').replaceChildren(renderAnswer(answer))", html)

    @unittest.skipUnless(shutil.which("node"), "Node is optional in the CI runner")
    def test_html_breaks_are_not_interpreted_as_arbitrary_html(self):
        # Load precisely the real in-browser parser's inline functions in a
        # minimal offline DOM, not a new renderer with matching test behavior.
        source = UI.read_text(encoding="utf-8")
        start = source.index("function appendInline(node,text){")
        end = source.index("function tableCells(line){", start)
        functions = source[start:end]
        script = r"""
const vm = require('vm');
class Element {
  constructor(name){this.name=name;this.children=[];this.textContent='';}
  appendChild(item){this.children.push(item);}
}
const document={
  createElement(name){return new Element(name);},
  createTextNode(value){const n=new Element('#text');n.textContent=value;return n;}
};
function appendMathText(node,value){node.appendChild(document.createTextNode(value));}
function answerTimestampNode(){return null;}
const context={document,appendMathText,answerTimestampNode};
vm.createContext(context);
vm.runInContext(process.argv[1],context);
const td=document.createElement('td');
context.appendInline(td,'**Peak**<br>1 W<br/>Original <script>alert("x")</script>');
const stringify=n=>n.name==='br'?'[BR]':(n.name==='#text'?n.textContent:n.name+'('+n.children.map(stringify).join('')+')');
const got=stringify(td);
if(got!=='td(strong(Peak)[BR]1 W[BR]Original <script>alert("x")</script>)'){
  throw new Error('Unsafe or incorrect multiline text rendering: '+got);
}
if(td.children.some(n=>n.name==='script'))throw new Error('Executable script element created');
"""
        result = subprocess.run(
            ["node", "-e", script, functions],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
