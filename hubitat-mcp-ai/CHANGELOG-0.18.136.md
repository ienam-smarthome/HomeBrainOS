# HomeBrainOS 0.18.136 — readable V2 test duration and status

- Measured duration shows **minutes + seconds** (e.g. 2 min 32.751 sec) and **total seconds** (152.751 seconds), instead of an opaque number of milliseconds. Raw millisecond precision is still present in the copyable technical JSON.
- Missing, invalid or negative duration values display “Unavailable”, never `NaN`.
- The “Command retention” measurement is relabelled “Commands retained (retrieved)” so it does not imply source history is complete.
- The result status now distinguishes tests stopped at the MCP read budget, AI planning timeout, unavailable planning and lack of approved reads from a fully completed investigation.
- No MCP, AI model, device or rule behaviour changed. V2 stays opt-in read-only and V1 continues as the production path.
