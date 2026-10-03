# Planner Review — SI-4-R8

Planner: ChatGPT  
Reviewed implementation CODE SHA: `a9d8c3dd1e06328b7c7fed339f82be31f7d5bfbb`  
Reviewed bookkeeping HEAD: `345a2ce6b14040a934c04de177b58e41121e862b`  
Pinned DSH: `0.2.0-rc.1` @ `4878cdabd87d4041bdaff61d04c966883b9fd07a`

## Verdict

**SI-4-R8 PARTIALLY ACCEPTED, NOT FINAL — SI-4-R9 REQUIRED**

R8 finally proves the core native DSH runtime chain with a real pinned
Context/ToolRuntime/AgentPresetRegistry and real `ctx.tools.execute(..., agent)`.

This is the first round where the native execution gate is genuinely closed.

However, final product freeze is still blocked by three narrow issues:

1. package-subpath resolution is not proven through an installed product bundle;
2. transport hydration still has fail-open/permissive defaults and raw-dict
   leakage for typed nested revision fields;
3. the native §7 qualification returned `conflict` instead of the planned exact
   no-approval `approval_required` outcome.

R9 is a narrow final semantic/package closure. Do not revisit the native runtime
architecture.

---

## What R8 genuinely proves

The committed harness
`integration/dsh/qualification/knowledge-curator-r8.mjs` now really:

- verifies pinned DSH HEAD;
- imports real pinned Cordis/DSH packages;
- creates real `Context`;
- mounts real `ToolRuntime`;
- mounts real `AgentPresetRegistry`;
- registers a real `knowledge-curator` preset;
- creates a real Agent;
- mounts the preset into that Agent;
- executes `ctx.tools.schemas(agent)`;
- executes `ctx.tools.execute(..., agent)` for commit and revision;
- exercises ToolRuntime input/output validation;
- executes the exact shipped plugin bytes as verified by SHA equality.

Observed real runtime evidence:

```
ctx.tools.schemas(agent)
= ["knowledge_curator_commit","knowledge_curator_revision"]

ctx.tools.schemas()
= []

commit ToolExecutionResult
= {
    "isError": false,
    "value": {
        "status": "published",
        "commit_attempted": true,
        "blocked_reason": null
    }
  }

revision ToolExecutionResult
= {
    "isError": false,
    "value": {
        "status": "conflict",
        "error": null
    }
  }
```

Therefore the following chain is now accepted as real:

```
Pinned DSH
 -> Context
 -> ToolRuntime
 -> AgentPresetRegistry
 -> Agent scope
 -> exact shipped bridge plugin
 -> defineTool
 -> ctx.tools
 -> JS spawn/stdin
 -> Python bridge
 -> application workflow
 -> ToolRuntime output validation
```

Do not ask Executor to re-prove this architecture from scratch in R9.

---

# Remaining blocker 1 — installed package-subpath resolution is still not proven

R8 report says:

`installed package subpath resolved: PASS`

but its evidence is:

`TestPackageSubpath::test_cordis_uses_package_subpath`

That test only checks that the YAML contains:

`@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`

It does not:
- pack the bundle;
- install the tarball into an isolated pinned DSH environment/profile;
- resolve the package export through Node/Loader;
- activate the product `cordis.patch.yml`;
- verify no broken preset/plugin diagnostic.

The real R8 native harness uses a copied `file:` URL fixture plugin, not the
installed product package subpath.

### Required R9 closure

Perform an actual package-level qualification:

1. `pnpm pack` the Knowledge Curator DSH bundle;
2. install the resulting tarball into an isolated pinned DSH environment/profile;
3. prove Node/DSH resolves:
   `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
4. activate the package's own `cordis.patch.yml`;
5. verify the `knowledge-curator` preset is not broken;
6. if practical, mount the installed preset and verify the two native tools are
   visible from the real Agent scope.

Do not substitute a YAML string assertion.

---

# Remaining blocker 2 — CurationReport safety fields still default permissively

Current bridge hydration still contains:

```python
metadata_valid=comp_raw.get("metadata_valid", True)
assertion_count=comp_raw.get("assertion_count", 0)
allows_formal_curation=comp_raw.get("allows_formal_curation", True)
requires_manual_review=comp_raw.get("requires_manual_review", False)
requires_return_upstream=comp_raw.get("requires_return_upstream", False)
returned_upstream_count=report_raw.get("returned_upstream_count", 0)
```

For a serialized prepared CurationReport transport boundary, these are
safety-relevant semantics.

Missing values should not automatically become permissive state unless the
accepted bridge serialization contract explicitly defines those fields as
optional with those exact defaults.

### Required R9 closure

Choose one contract and test it:

#### Preferred
Require these fields explicitly and fail closed if absent.

At minimum:
- completeness.metadata_valid
- completeness.assertion_count
- completeness.allows_formal_curation
- completeness.requires_manual_review
- completeness.requires_return_upstream
- returned_upstream_count

#### Alternative
If there is an existing accepted serialized contract making them optional,
document the source of that contract and test the exact schema-defined defaults.

Do not silently invent permissive upstream state.

---

# Remaining blocker 3 — RevisionPackage nested typed fields are still not hydrated

Current R8 bridge passes:

```python
unchanged_pairs=cd_raw.get("unchanged_pairs") or []
modified_pairs=cd_raw.get("modified_pairs") or []
```

directly into `ContentDeltaPlan`.

Frozen schema requires those items to be `AlignedPair` instances, not raw dicts.

Current bridge also does not hydrate:
- `carried_records` -> `CarriedAssertionRecord`
- `transitions` -> `AssertionTransition`

If non-empty values are supplied, typed domain models can contain raw dicts or
the data can be silently dropped.

### Required R9 closure

Faithfully hydrate:

#### AlignedPair
- prior_unit_id
- new_unit_id
- category -> `DeltaCategory`

#### CarriedAssertionRecord
- old_assertion_id
- carried_assertion_id
- unit_id

#### AssertionTransition
- action -> `TransitionAction`
- old_assertion_id
- new_assertion_id
- slot_key
- reason

Invalid enum or missing required identifier -> fail closed.

If any nested structure is intentionally unsupported, reject non-empty supplied
values explicitly. Never pass raw dicts or silently discard them.

---

# Remaining blocker 4 — native §7 fixture result is not the planned exact outcome

R8 native execution is real, but the no-approval revision returned:

`conflict`

The R8 plan required the qualification fixture to produce an exact predictable
no-approval result:

`approval_required`

The harness itself prints the §7 check as FAILED when it sees conflict, but the
process still exits 0.

That means the harness command exit code is not a sufficient pass/fail signal
for the acceptance assertions.

### Required R9 closure

Fix the seeded qualification state/request so that a no-approval native revision
through real `ctx.tools.execute` deterministically returns:

`approval_required`

Then the harness must throw/exit nonzero if:
- native tool names are missing;
- §5 is not published;
- §7 is not approval_required;
- any ToolExecutionResult has `isError=true`;
- package/runtime assertions fail.

Do not only print `FAILED` and continue to exit 0.

A second valid-approval native case reaching `finalized` is desirable but not
required if frozen SI-2B already proves approval-finalization semantics.

---

# R9 final acceptance gate

SI-4 can be frozen only when:

1. real pinned native execution from R8 remains passing;
2. installed package subpath resolution is genuinely proven;
3. CurationReport safety-relevant fields are fail-closed or explicitly governed
   by an accepted serialization contract;
4. RevisionPackage nested typed fields are faithfully hydrated/rejected;
5. native no-approval §7 result is exactly `approval_required`;
6. R9 harness exits nonzero on failed assertions;
7. public MCP remains exactly four;
8. frozen core/workflow files remain unchanged;
9. all mandatory regressions remain green.

---

## Planner disposition

Active phase: SI-4-R9.

R9 is a final narrow closure, not a new architecture round.

STOP after R9 and return for final Planner acceptance.
