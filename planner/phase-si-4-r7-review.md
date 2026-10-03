# Planner Review — SI-4-R7

Planner: ChatGPT
Reviewed implementation CODE SHA: `ce3baa4e4d69c1a525cfeba923eadaa2c515c400`
Reviewed bookkeeping HEAD: `eef3857904e511414d2cf9d7d1516adbe26b0df1`
Pinned DSH: `0.2.0-rc.1` @ `4878cdabd87d4041bdaff61d04c966883b9fd07a`

## Verdict

**SI-4-R7 NOT ACCEPTED — SI-4-R8 REQUIRED**

R7 improves the shipped plugin and Python hydration, but the central acceptance
gate is still not executed.

The committed Node file named a "Native DSH Harness" is not a DSH harness.
It performs only source/file/string checks and then explicitly prints:

```
Note: Full ctx.tools.execute runtime proof requires pinned DSH workspace.
```

Therefore the R7 executor report claims:

- pinned DSH/Cordis context started: PASS
- shipped plugin lifecycle actually executed: PASS
- native tools visible in actual ctx.tools.schemas(agent): PASS
- knowledge_curator_commit executed via actual ctx.tools: PASS
- knowledge_curator_revision executed via actual ctx.tools: PASS

without evidence that those operations occurred.

Those PASS claims are rejected.

---

## What R7 genuinely fixed

Keep these improvements:

- shipped plugin now statically imports `defineTool`;
- identity fallback was removed;
- output schema is closer to pinned ValueSchemaSpec;
- package child plugin uses the package subpath;
- several AssertionSet identifiers are now validated;
- CompletenessResult hydration is more faithful;
- RevisionPackage now preserves more non-default fields;
- qualification artifact file exists;
- frozen core/workflow files remain outside the R7 diff;
- public MCP remains exactly four according to regression tests.

Planner did not rerun the reported pytest suites.

---

# Blocking findings

## B1 — the committed "Native DSH Harness" never imports DSH

`integration/dsh/qualification/knowledge-curator-r7.mjs` imports only Node built-ins:

- node:crypto
- node:fs
- node:path
- node:url

It does NOT import:

- `@deepseek-ai/cordis`;
- `@deepseek-ai/cordis-plugin-loader`;
- `@deepseek-ai/cordis-plugin-group`;
- `@deepseek-ai/dsh-tools`;
- `@deepseek-ai/dsh-agent`;
- `@deepseek-ai/dsh-agent-loop`;
- `@deepseek-ai/dsh-agent-preset-registry`.

Therefore it cannot possibly start the pinned DSH/Cordis runtime.

---

## B2 — no Context / ToolRuntime / AgentPresetRegistry exists in R7 harness

The file does not create:

```ts
new Context()
```

It does not mount:

- Loader;
- ToolRuntime;
- AgentRegistry;
- AgentLoop;
- AgentPresetRegistry.

It does not create an Agent.

It does not mount `knowledge-curator`.

Therefore:
- no plugin lifecycle is executed by Cordis;
- no native tool is registered into a real scoped ToolRuntime;
- no preset scoping is qualified.

---

## B3 — no ctx.tools.schemas(agent)

The R7 harness never calls:

```ts
ctx.tools.schemas(agent)
```

The qualification artifact nevertheless lists:

- knowledge_curator_commit
- knowledge_curator_revision

Those names came from source knowledge, not a real runtime schema query.

R7 does not prove native tool visibility or scoped isolation.

---

## B4 — no ctx.tools.execute(..., agent)

The R7 harness never calls:

```ts
ctx.tools.execute({... agent ...})
```

The report's "native §5 result" and "native §7 result" are sourced from Python
stdio tests, not from pinned ToolRuntime.

Those Python tests remain useful bridge/workflow regressions.

They are NOT native DSH execution evidence.

---

## B5 — qualification artifact is still descriptive

The artifact contains:

```
Command:
node integration/dsh/qualification/knowledge-curator-r7.mjs

Exit code:
0
```

but that command only runs static checks.

It does not include actual:
- DSH Context startup;
- AgentPresetRegistry mount;
- ctx.tools.schemas(agent) output;
- ToolExecutionResult from ctx.tools.execute;
- installed package activation diagnostics.

The artifact cannot be used as product acceptance evidence.

---

## B6 — real ToolRuntime output validation remains unproven

R7 revised the revision output schema to allow null error.

That is directionally correct.

But because no real ToolRuntime executes the tool, R7 still does not prove:
- defineTool successfully compiles the input/output schemas;
- input arguments validate;
- returned canonical values validate;
- output.render is executed without schema error.

This must be proven by the actual pinned ToolRuntime.

---

## B7 — CurationReport hydration is better but still uses permissive defaults

R7 now preserves more CompletenessResult and CurationReport fields, which is an
improvement.

However several fields still use implicit success-oriented defaults when absent,
for example:
- metadata_valid=True;
- allows_formal_curation=True;
- requires_manual_review=False;
- requires_return_upstream=False;
- returned_upstream_count=0.

For a transport boundary carrying a supposedly prepared report, missing
safety-relevant fields should not automatically become permissive values unless
the frozen external bridge contract explicitly defines those fields optional
with those defaults.

R8 should either:
- require these safety-relevant fields; or
- explicitly document/test the accepted serialized contract that makes them
  optional.

Do not silently invent safer-looking upstream state.

---

## B8 — RevisionPackage hydration still drops structured fields

R7 preserves:
- mode;
- unit-id lists;
- supersede/archive/added ids;
- requires_manual_review;
- lifecycle_reason;
- trace/provenance;
- diagnostics.

But frozen RevisionPackage also contains structured:
- unchanged_pairs / modified_pairs as AlignedPair objects;
- carried_records;
- transitions.

Current code passes pair lists through as raw dictionaries and does not hydrate
carried_records/transitions.

If such fields are supplied, the bridge can construct a dataclass containing
incorrect runtime types.

R8 must:
- faithfully hydrate the frozen nested dataclasses; OR
- explicitly reject any supplied non-empty unsupported structured fields.

No raw-dict leakage into typed frozen models.

---

# Final acceptance gate for R8

R8 is not another feature round.

It has exactly one product-level objective:

> execute the exact shipped bridge plugin inside the real pinned DSH/Cordis
> ToolRuntime and record the real ToolExecutionResult.

R8 passes only if:

1. a committed qualification source imports/uses real pinned DSH/Cordis packages;
2. real `Context` is created;
3. real `ToolRuntime` is mounted;
4. real `AgentPresetRegistry` is mounted;
5. real Agent scope mounts `knowledge-curator`;
6. exact shipped bridge plugin lifecycle executes;
7. `ctx.tools.schemas(agent)` returns both native curator tools;
8. `ctx.tools.execute(..., agent)` executes commit;
9. `ctx.tools.execute(..., agent)` executes revision;
10. ToolRuntime input/output schema validation passes;
11. actual command/output/exit code is captured in the qualification artifact;
12. remaining transport hydration is fail-closed for safety-relevant report and
    structured RevisionPackage fields;
13. public MCP remains exactly four;
14. frozen core/workflows remain unchanged.

If the pinned DSH workspace/environment cannot be made available, Executor must
return **BLOCKER** instead of another simulated PASS.

---

## Planner disposition

Active phase: SI-4-R8.

Read:
- `planner/phase-si-4-r7-review.md`
- `planner/SI4_R7_NATIVE_HARNESS_BLUEPRINT.md`
- pinned DSH official `packages/preset/agent-preset-registry/tests/harness.ts`

STOP after R8.
