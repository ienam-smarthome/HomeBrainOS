# HomeBrainOS v0.18.293 — Stage 4O: Ollama Cloud benchmark failure diagnostics

The v0.18.292 dashboard displayed a generic "Cloud test failed or returned an invalid assessment", without distinguishing a provider rejection from a timeout or malformed model output. It also demanded un-fenced JSON from a cloud model even though [Ollama's Structured Outputs documentation](https://docs.ollama.com/capabilities/structured-outputs) explicitly states that Ollama Cloud currently does not support schema-enforced structured output.

**Changes**
- Keep the same existing Ollama account, configured model and consent-based one-case cloud test. No extra credentials, GitHub workflow, hub/device or user-history access.
- For the benchmark's single non-streaming cloud call, request the final text with optional model thinking disabled. This changes only the benchmark request, not general HomeBrain agent thinking.
- Accept one bounded plain JSON object or a single Markdown JSON-fenced object. Reject extra prose, multiple objects, partial assessments, unknown IDs and unsupported verdicts. Do not guess or fabricate model decisions.
- Categorise errors safely: HTTP 400 request parameters; 401/403 credentials/permissions; 404 unknown endpoint/model; 429 quota; 5xx provider error; timeout; transport error; empty text; invalid JSON; semantically invalid JSON fields; unexpected failure. No provider exception body, raw prose, prompt, token, private URL or stack trace returned through API.
- Continue **one request per explicit button press, no retries**, with cooldown, hourly bound, no MCP reads and no live device changes.
- Add mocked transport tests covering fenced JSON, rejected extra content, all error categories, no retries, secret redaction and independent synthetic scorer limitations.

**What to test after upgrading**
Open the HomeBrain dashboard **Ollama Cloud benchmark** and choose **Lighting**. Tick consent and press Run once. If successful, inspect the model paragraph and 4/4 synthetic claims; if it fails, share only the displayed error message (never the API key). A failure is not evidence that the model has poor reasoning. Every click may use Ollama allowance.

**No claim of verified real cloud quality:** CI tests use mock transports only. Source assertions are synthetic; passing the benchmark does not certify full prose, evidence-retrieval skill or an improved production publisher. No live cloud requests are made by CI.

Rollback: revert this release and restore v0.18.292 if needed.
