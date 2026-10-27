---
doc_id: "HIST-20261027-CARD299-CODEX"
title: "Card 299 standalone leaf-runtime guard coverage"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-27T12:55:39+09:00"
updated: "2026-10-27T12:55:39+09:00"
source_of_truth: "Git"
---

# Card 299 standalone leaf-runtime guard coverage

## Scope

Claude's Card 298 review proved that fourteen defensive guards worked when targeted directly but
could be removed without failing the repository suite. Card 299 adds behavioral witnesses only;
the standalone runtime, worker, lock, and rotation product code are unchanged. This branch starts
from train 77 so the coverage also exercises the subsequently landed bytecode and worker-module
closure without restacking older product code.

## Added witnesses

The focused suite now independently refuses:

- a successful HTTP response whose final URL differs from the pinned URL;
- a pre-imported dependency outside the installed runtime and an exact-version mismatch inside it;
- duplicate wheel members, absolute paths, and backslash paths;
- a semantically equal but non-canonical bundle manifest;
- receipt count, installed-file digest, and worker-module digest disagreement;
- colliding paths across selected wheels and an oversized uncompressed runtime;
- a relative runtime destination;
- dangling bundle-output and runtime-directory symlinks; and
- both directory and file symlinks inside an installed runtime.

The test writes the backslash ZIP fixture using Linux parser semantics so Windows normalization
cannot turn the hostile member into a forward-slash path before the product sees it. Symlink cases
are declared Linux-only and run in the hosted Backend lane.

## Mutation evidence

`tools/test_c298_mutations.py` retains M1–M10 and adds M11–M26. M11–M21 and M23–M25 cover the
fourteen original review classes exactly; M22 adds the new dangling-output-symlink boundary, and
M26 adds the E8 bounded-regular-file boundary. The M26 runner also proves that only its dedicated
symlink/directory witness fails while the remainder of the runtime suite passes.
The runner restores byte-for-byte originals after every mutant and counts only pytest exit code 1
as a kill. On Windows the non-symlink cases are **21/21 killed** and four Linux symlink mutants are
explicitly skipped together with M26; the Backend Python 3.12 job runs the same tool on Linux and
requires all **26/26** to die. Python 3.14 continues to exercise the actual-wheel lifecycle without duplicating
the mutation cost.

Local focused result before push: **32 passed, 6 declared Linux-only skips**; mutation result:
**21 killed, 5 declared Linux-only skips**. Hosted Linux completion remains a review condition and
must not be inferred from the local result.

## Review handoff

Reviewer: Claude. Confirm each prior survivor has a behavioral witness, M11–M26 remove the intended
guards one at a time, the Linux job executes (rather than skips) all symlink cases, and no product
runtime file changed.
