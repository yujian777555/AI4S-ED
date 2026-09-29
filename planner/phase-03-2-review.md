# Phase 3.2 Planner Review — Package/Loader Accepted, Runtime Activation Pending

**Implementation:** `eddd2e2e73f980bd883e38388fa5067f2340e034`  
**origin/main bookkeeping tip:** `fad02cd9f3ec05e2ee69bd00768302478d92cf5f`  
**integration/dsh tests:** 60 passed / 0 failed  
**knowledge_curator tests:** 127 passed / 0 failed  
**Verdict:** **PARTIAL PASS — package/source/Loader accepted; preset runtime activation not yet proven**

## Accepted

The following Phase 3.2 claims are supported by the actual implementation:

- official DeepSeek Harness source is pinned to `4878cdabd87d4041bdaff61d04c966883b9fd07a`;
- source reports/builds as `0.2.0-rc.1`;
- Node `v24.9.0` satisfies the upstream engine range;
- pnpm `11.7.0` matches the upstream package-manager pin;
- the product artifact is a configuration-only DSH bundle;
- exactly one `knowledge-curator` Agent Preset is declared;
- product bundle does **not** own `@deepseek-ai/dsh-agent-preset-registry`;
- persona stays within knowledge_curator scope;
- MCP child points to `knowledge_curator.mcp_server`;
- no API key is passed to the MCP subprocess;
- real 0.2 DSH `--dump-config` accepts the product patch and resolves its plugin names;
- 60 integration test functions were mechanically counted;
- no §6/§7 or neighboring Agent scope was added.

## Important correction: Loader qualification is not runtime activation

The Phase 3.2 report labels:

`knowledge-curator preset activation: PASS`

but the implementation only executes:

```text
pnpm dsh ... --patch ... --dump-config
```

That proves composition/config resolution. It does **not** activate the Cordis rows, create the registry's standing preset scope, spawn the MCP child, or run `AgentPresetRegistry.diagnostic()` against a live mounted tree.

The qualification script currently derives `preset_broken=false` by looking for the word `broken` in dump output. This is not a runtime activation check.

Therefore accepted wording is:

- **source build: PASS**
- **real Loader/config qualification: PASS**
- **preset runtime activation: NOT YET TESTED**
- **preset mount: NOT YET TESTED**

This is not a regression in the product bundle; it is an evidence/qualification gap.

## Packaging issue P3.2.1-01 — wildcard DSH dependencies

The product `package.json` currently contains:

```json
"dependencies": {
  "@deepseek-ai/dsh-agent-preset": "*",
  "@deepseek-ai/dsh-persona": "*",
  "@deepseek-ai/dsh-mcp-client": "*"
}
```

For a configuration-only bundle this is unsafe and unnecessary.

The official DSH configuration-only MCP bundle template declares only:
- name;
- version;
- type;
- `dsh.bundle.patch`;

and relies on the running DSH installation's own plugin resolution.

Using `"*"` can cause a local bundle install to pull a newer preset/persona/MCP package than the pinned 0.2.0-rc.1 host, recreating CG-015 inside the package tree.

Phase 3.2.1 must remove these wildcard dependencies unless the pinned 0.2 runtime demonstrably requires exact dependencies. If exact package dependencies are truly required, pin exactly `0.2.0-rc.1`; never use `"*"`.

## Correct runtime qualification seam

The pinned upstream provides an official preset-aware test/host path.

The Web scaffold:
- boots the real shipped Web composition;
- owns the global preset registry;
- supports profile-installed local bundles;
- exposes the live root `ctx`.

Official upstream tests create Agents with:

```ts
ctx.agents.create({
  sessionId,
  setup: agentCtx =>
    ctx.agentPresets.mount(agentCtx, 'knowledge-curator')
})
```

This is the correct contract because `mount()` is designed for an unpublished Agent in its `setup` callback.

Do **not**:
- mount after `agent/created`;
- patch upstream `sdk/server.ts`;
- make the product bundle own the root Agent factory.

## Next

Proceed to **Phase 3.2.1 — real preset activation/mount + preset-aware live DeepSeek smoke**.

If that phase passes, CG-015 can be closed and the knowledge_curator DSH Agent package can be considered runtime-qualified.
