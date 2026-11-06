# HomeBrainOS 0.18.434 — actionable source-qualified incident AI reports

- Preserve existing verified Hubitat event/startup findings and the conservative guard against model-invented causes.
- When a definitive unsupported model draft is withheld or empty, append host-authored, evidence-specific **Read-only next checks** instead of stopping at the rejection warning.
- Track failed app-mode historical-log requests separately from successful generic date-bounded log reads; never equate a generic log request or archived receipt count with reviewed app-specific messages.
- Explain missing pre-reboot resource samples and Historical Journal gaps rather than reconstructing unavailable histories.
- Emit `incident_source_coverage` in Technical details to distinguish authenticated Hub Events, app-mode log attempts and bounded generic log receipts; preserve the independent model hypothesis coverage flags.
- Clarify that the restart trigger may be verified while the originating memory consumer remains unverified.
- No extra Hubitat requests, changes to tools, write permissions, recurring processing, new configuration or automatic paid model escalation.
- Regression coverage reproduces both 5 November incident patterns and generic-log fallback ambiguity.
