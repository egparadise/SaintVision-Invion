FLEET5 setup integration failure record (2026-11-05, owner Codex)

The preliminary docs gate exited 1: imported DB and consecutive-rotation reviewer histories link to the actual Low closure review d254fc6a, which was not yet in the root base or the explicitly named reviewer subset. No result was rewritten. The corrective action imports only that real commit's two History/Evidence files; no shared board or registry changes are included. A new docs observation is required before committing the correction.

The ordinary rotation merge stopped with a real Card150 content conflict (merge exit1). Resolution retained the new DB prepare pair from d18f/864b and the actual LAN tooling pair from 6fc, while preserving every other JSON field against report base142b. This is recorded as conflict resolution, not as evidence that 6fc or a combined SHA was independently accepted.

The first required-doc read through a Python stdin literal failed because the host shell encoded Korean path characters as question marks. Reading canonical UTF-8 files with PowerShell -LiteralPath corrected the access; no repository file was changed by the failed read.
