# Phase 3.1.1 Planner Review — MCP Bridge Accepted

**Implementation:** `47bd16cc467905810246bf8049008d5748f97ecf`  
**Merged origin/main:** `ca461b4b8ad10b7ed2242a9e8c6e1c5b7897ab5e`  
**Integration/keyless tests:** 49 passed / 0 failed  
**knowledge_curator tests:** 127 passed / 0 failed  
**Strict live MCP smoke:** PASS  
**Verdict:** **PASS — Python MCP bridge accepted and frozen**

## Exact live evidence

The accepted run contains exactly one matching call:

```text
event.type = tool/call
event.seq = 10
event.data.name = mcp__knowledge_curator__curate_assertion_set
```

and exactly one linked result:

```text
event.type = tool/result
event.seq = 11
sourceEventSeqs = ["10"]
isError = false
```

The three independently derived summaries match:

```text
A direct KnowledgeCurator core:
  successful / accept / medium

B actual linked DSH tool/result:
  successful / accept / medium

C model final response:
  successful / accept / medium
```

Therefore `A == B == C` is established from real DSH Session events, not string heuristics.

## Additional accepted hardening

- heuristic tool-name occurrence counting was removed;
- call arguments are represented only by a bounded hash/ref-id summary;
- `credential_available` and `secret_leaked` semantics are separated;
- live artifact reports `secret_leaked=false`;
- malformed MCP payloads now use the official MCP 2.2.0 `ToolError` path and surface as `isError=true`;
- no §5 business logic was duplicated in MCP;
- no Agent Preset / §6 / §7 scope creep occurred.

## Merge conflict review

The final merge `ca461b4...` changes only the Planner-owned `status.json` resolution state relative to the Planner handoff. The implementation commit `47bd16c...` remains in history and is the accepted Phase 3.1.1 implementation.

## Frozen integration baseline

Accepted:
- knowledge_curator §5.1–§5.4 core;
- Python MCP server `mcp==2.2.0`;
- DSH-facing public tool `mcp__knowledge_curator__curate_assertion_set`;
- DSH 0.1.5rc1 live API + MCP evidence path.

Do not rewrite these silently in later phases.

## Next

Proceed to Phase 3.2: source-pinned DSH 0.2.0-rc.1 Agent package / preset contract qualification.
