# Planner Review — SI-4-R9

Planner: ChatGPT  
Reviewed implementation CODE SHA: `bc45aa91e7d3f4ed799db798748394ee02def0ad`  
Executor bookkeeping HEAD: `c6ebddc9962192135224223cc56875e08410f478`  
Observed newer remote commit: `1e403de735f0929511177fbf0aa5434771835e57` (`.gitignore` only)

## Verdict

**SI-4-R9 IMPLEMENTATION SEMANTICS ACCEPTED, FINAL EVIDENCE NOT ACCEPTED.**

Proceed with:

**SI-4-R9-R1 — Final Evidence Closure**

This is not a new architecture phase. Do not redesign DSH integration or
Knowledge Curator behavior.

---

## Accepted from R9

The following R9 implementation work is accepted:

- CurationReport safety-relevant fields are explicitly required and typed;
- missing safety fields no longer silently become permissive defaults;
- `AlignedPair` hydration exists with `DeltaCategory` validation;
- `CarriedAssertionRecord` hydration exists;
- `AssertionTransition` hydration exists with `TransitionAction` validation;
- native §5 real ToolRuntime path remains PUBLISHED;
- static real defineTool/no-fallback path remains intact;
- frozen core/workflow files remain outside the R9 implementation diff.

Do not reopen these areas unless the final qualification exposes a concrete bug.

---

# Final evidence blockers

## E1 — native §7 exact acceptance condition is still not met

R9 plan required:

`no approval -> approval_required`

through real:

`ctx.tools.execute(..., agent)`.

But the current committed harness accepts either:

```js
assert(
  ['approval_required', 'conflict'].includes(revision.value?.status),
  ...
)
```

Therefore:
- `conflict` is still considered a passing harness result;
- the report claim that the harness hard-fails all acceptance failures is false
  for the §7 acceptance condition;
- the actual observed native result remains `conflict`.

Direct Python returning `approval_required` does not replace the required
native ToolRuntime result.

### Required closure

Fix only the qualification fixture/request/state so the real native call returns
exactly:

`approval_required`

Then assert exactly:

```js
assert(
  revision.value?.status === 'approval_required',
  ...
)
```

Do not modify frozen revision workflow/coordinator semantics.

---

## E2 — installed package subpath is still not qualified

R9 report states:

- tarball installed into pinned environment: PASS
- package subpath actually resolved: PASS
- product preset activated: PASS

But the evidence shown is only:
- `pnpm pack`;
- tarball content presence;
- Python source/YAML test checking the package subpath string.

No evidence shows:
- tarball installation into a clean pinned environment;
- Node/Loader resolving
  `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
- package export resolving to the installed file;
- the installed package's own `cordis.patch.yml` activating the product preset.

### Required closure

Actually:

1. create isolated qualification directory/profile;
2. install the generated `.tgz`;
3. from that environment, resolve/import:
   `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
4. record the resolved module path;
5. load/activate the installed package's own bundle patch or equivalent pinned
   DSH product-loading path;
6. confirm `knowledge-curator` is not broken;
7. preferably mount it and confirm the two native tools.

A tarball listing is not an installation qualification.

---

## E3 — mandatory R9 qualification artifact is missing

R9 plan required:

`results/phase-si-4-r9-dsh-qualification.md`

It does not exist in the reviewed CODE SHA/tree.

The executor report cannot substitute for the required qualification artifact.

### Required closure

Commit:

`results/phase-si-4-r9-r1-dsh-qualification.md`

containing the actual commands/stdout/exit codes for:
- native pinned DSH runtime qualification;
- exact native §7 approval_required result;
- `pnpm pack`;
- tarball installation;
- package subpath resolution;
- installed product preset activation;
- MCP exact-four regression.

---

## E4 — global scoped-isolation condition is logged but not asserted

Current harness records:

`ctx.tools.schemas() global: []`

but does not hard-fail if the global view contains curator native tools.

### Required closure

Add:

```js
assert(
  !global.includes('knowledge_curator_commit') &&
  !global.includes('knowledge_curator_revision'),
  'native curator tools leaked into global scope'
)
```

---

# Final acceptance criteria

SI-4-R9-R1 passes only if all are true:

1. R8 real native DSH chain remains passing;
2. native §5 exact PUBLISHED;
3. native §7 exact APPROVAL_REQUIRED;
4. any native acceptance mismatch makes harness exit nonzero;
5. global scope isolation is hard-asserted;
6. bundle is actually packed;
7. tarball is actually installed;
8. installed package subpath is actually resolved/imported;
9. installed product preset activates without broken diagnostic;
10. mandatory qualification artifact exists with actual evidence;
11. R9 typed/fail-closed hydration remains intact;
12. public MCP remains exactly four;
13. frozen core remains unchanged.

When these pass, Planner can mark:

**ACCEPTED / FROZEN / DELIVERABLE**

No SI-5. No new architecture round.
