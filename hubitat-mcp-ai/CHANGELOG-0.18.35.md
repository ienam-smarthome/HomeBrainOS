# v0.18.35 — Show and reopen recent HomeBrain chats (browser-local)

## Confirmed 0.18.34 gap
The existing HomeBrain UI renders only the latest answer. The browser retains at most eight message entries in `sessionStorage` for same-tab follow-up context, but there is no conversation picker or New Chat action. A browser restart, tab replacement or add-on update may make old conversations inaccessible. This is not an MCP or AI response failure.

## Changes
- Show a compact, always-visible **Chats** strip above the Ask box, including **+ New chat**, selectable saved chat titles, and per-chat deletion with confirmation.
- Save a bounded set of last 20 conversations / 32 messages per chat (up to 6,000 characters per stored message) using the current browser's local storage. This is **browser-local, plaintext, not encrypted, not shared between phones/PCs**, and not a Hubitat or HomeBrain server archive. The browser visibly discloses these limits and shared-device risk.
- Preserve a legacy in-tab `hmcp_history_<sessionId>` last-eight-message snapshot when possible; there is **no mechanism to reconstruct older deleted or evicted history**. New conversations start with fresh session IDs and clean context.
- Reopen old chats by showing earlier messages plus the saved last answer, without reactivating any old confirmation, device action, firmware update button, choice prompt or automatic answer speech.
- Switching or deleting an active chat cancels a running request and advances the local sequence so a delayed response cannot be displayed in a different conversation.
- Sending a new question appends the successful question and answer, shows previous turns, keeps only the last eight entries for the API's conversational context, and preserves the original model-tier request selection.
- Keep existing Free as the default selection each time New Chat or a saved chat is opened. The older explicit Auto, DeepSeek Paid and Claude Paid options remain unchanged.

## Security and scope
Store only user-visible question/answer text, not technical JSON, API keys, MCP receipts, model tool arguments or automatic provider payments. The storage belongs to the browser profile; users must delete chats on shared devices. Do not assume Home Assistant ingress local storage is encrypted or synced. This feature creates **no new backend conversation API**, no external cloud sync, no Hubitat mutations and no MCP permission changes.

## Verification
Static/JavaScript syntax regression tests cover visible session controls, correct session_id/request_id submission, safe cross-chat cancellation, bounded browser storage, confirmation/replay protection, preservation of existing UI controls, Free default and legacy session migration. Review all three GitHub CI workflows before merge; browser live testing after add-on upgrade remains necessary.
