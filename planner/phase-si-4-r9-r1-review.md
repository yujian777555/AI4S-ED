# Planner Review — SI-4-R9-R1

Planner: ChatGPT  
Reviewed implementation CODE SHA: `9591cd3212e18e9f653dc1b9a7707a9ee0044ff4`  
Reviewed bookkeeping HEAD: `5b02a634e04d5e5596b294fd262b1ed0730a23d6`

## Verdict

**SI-4-R9-R1 CORE EVIDENCE ACCEPTED, ONE PRODUCT-ACTIVATION EVIDENCE GAP REMAINS.**

Proceed with:

**SI-4-R9-R2 — Installed Product Preset Activation Evidence**

This is evidence-only. No business-code redesign.

---

## Accepted from R9-R1

The following are now accepted and MUST NOT be reopened unless a concrete
regression appears:

1. real pinned DSH native execution chain;
2. exact shipped plugin SHA equality in the pinned workspace qualification;
3. `ctx.tools.schemas(agent)` contains:
   - `knowledge_curator_commit`
   - `knowledge_curator_revision`;
4. native §5 exact `PUBLISHED`;
5. native §7 exact `APPROVAL_REQUIRED`;
6. ToolRuntime input/output validation;
7. R9 fail-closed CurationReport hydration;
8. typed `AlignedPair`, `CarriedAssertionRecord`, `AssertionTransition`
   hydration;
9. `pnpm pack`;
10. clean tarball installation;
11. installed package subpath import:
    `@ai4s-ed/knowledge-curator-dsh/runtime/bridge-plugin.js`;
12. installed module exposes:
    - `name === "curator-bridge"`
    - `typeof apply === "function"`;
13. mandatory R9-R1 qualification artifact now exists;
14. public MCP exact-four regression remains green.

Reported mandatory regression baselines:
- knowledge_curator: 522 passed;
- integration/system: 190 passed;
- integration/dsh: 109 passed.

Planner did not independently rerun those suites.

---

# Remaining evidence gap E1 — installed product patch/preset activation not proven

R9-R1 proves the tarball can be installed and the exported bridge subpath can be
imported.

It does **not** prove that the installed tarball's own:

`@ai4s-ed/knowledge-curator-dsh/cordis.patch.yml`

is consumed by the pinned DSH product/bundle loading path and results in a
healthy `knowledge-curator` preset.

The qualification artifact contains no actual:
- resolved installed `cordis.patch.yml` path;
- pinned Loader/app-boot activation command using that installed patch;
- preset resolution result;
- broken/not-broken result for the installed preset.

There is historical Phase 3.2 source-bundle evidence showing the product patch
can be consumed by pinned DSH and the preset is declared/not broken, but that
used the source checkout patch rather than the newly installed tarball.

### Required final closure

Using the **clean installed tarball environment** from R9-R1:

1. resolve the installed package's own:
   `@ai4s-ed/knowledge-curator-dsh/cordis.patch.yml`;
2. invoke the pinned DSH Loader/app-boot/profile path with that installed patch;
3. prove:
   - exit code = 0;
   - `knowledge-curator` preset is declared;
   - preset has no broken diagnostic;
4. preferably mount the installed preset into a real Agent and record the two
   native tools.

If the installed patch activation exposes a package bug, make only the narrow
package metadata/patch fix required.

---

# Evidence mismatch E2 — global isolation is observed but not hard-asserted

R9-R1 report says:

`global scope isolation hard-asserted: PASS`

but the committed native harness currently only records:

`ctx.tools.schemas() global: []`

It does not assert that curator tools are absent.

The observed runtime result `[]` is good and supports isolation, but the report
overstates the harness behavior.

### Required final closure

Add an explicit assertion:

```js
assert(
  !global.includes('knowledge_curator_commit') &&
  !global.includes('knowledge_curator_revision'),
  'native curator tools leaked into global scope'
)
```

Then rerun the native harness once.

No other native-harness behavior needs redesign.

---

# Final acceptance gate

SI-4-R9-R2 passes when:

1. installed tarball's own `cordis.patch.yml` is resolved from
   `node_modules/@ai4s-ed/knowledge-curator-dsh`;
2. pinned DSH consumes that installed patch successfully;
3. installed `knowledge-curator` preset is declared and not broken;
4. global scope isolation is explicitly asserted;
5. R9-R1 native §5/§7 exact results remain passing;
6. public MCP remains exactly four;
7. frozen core/workflows remain unchanged;
8. no business/transport semantics are reopened.

Then Planner will mark:

**ACCEPTED / FROZEN / DELIVERABLE**

No SI-5 and no further architecture phase.
