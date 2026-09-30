# Phase 5.2 Plan — Structured Content Delta + Assertion Transition Revision Package

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Implement the knowledge_curator-owned deterministic planning layer for docs/03 §7.1:

VersionUpgradeIntent
→ compare prior/new structured content units
→ identify unchanged/modified/added/removed scope
→ request extraction only for changed/new units when safe
→ combine carried-forward unchanged assertions with delta-extracted assertions
→ compute assertion transitions
→ build a deterministic RevisionPackage / RevisionDraft input for frozen §7.3 lifecycle publication.

This phase DOES NOT implement PDF/XML parsing or cross-module crawling.

## 1. Architecture boundary

knowledge_curator receives structured content manifests from upstream.

Do NOT:
- parse PDF/XML/LaTeX;
- run OCR;
- invent paragraph boundaries;
- use embeddings/edit distance/LLM to align paragraphs;
- crawl arXiv/Crossref/TOCs;
- change Phase 5.0 lifecycle semantics;
- change Phase 5.1 identity/lineage semantics;
- expose a new public MCP mutation tool;
- fake cross-store ACID publication in this phase.

CG-020 governs the temporary internal content-delta compatibility model.

## 2. Internal content-unit models

Add INTERNAL temporary schemas, recommended:
knowledge_curator/schemas/version_delta.py

### ContentUnitKind
At least:
- TEXT
- TABLE
- CHART
- FORMULA
- OTHER

### ContentUnit
At least:
- unit_id: stable identity within a source version;
- locator: page/section/object locator for that version;
- kind;
- content_hash;
- prior_unit_id: optional explicit cross-version alignment;
- metadata optional.

content_hash is supplied by upstream or deterministically computed over canonical upstream payload.
knowledge_curator must not hash inaccessible raw PDF bytes.

### VersionContentManifest
At least:
- source_version_id;
- ref_id;
- source_fingerprint;
- units[];
- trace_id;
- provenance_id.

Require unique unit_id within one manifest.

## 3. Exact cross-version alignment

For each NEW content unit, align to prior by this precedence:

1. prior_unit_id if explicitly supplied;
2. same unit_id only when prior_unit_id is absent;
3. otherwise no alignment.

Validation:
- one new unit cannot align to multiple prior units;
- one prior unit cannot be claimed by multiple new units;
- explicit prior_unit_id must exist;
- conflicting duplicate ids fail closed.

No fuzzy fallback.

## 4. Content delta classification

Produce ContentDeltaPlan with exact categories:

### UNCHANGED
Aligned prior/new unit and content_hash equal.

### MODIFIED
Aligned prior/new unit and content_hash differ.

### ADDED
New unit has no prior alignment.

### REMOVED
Prior unit is not aligned by any new unit.

Output at least:
- unchanged pairs;
- modified pairs;
- added new units;
- removed prior units;
- extraction_unit_ids;
- mode;
- diagnostics.

extraction_unit_ids =
- all MODIFIED new unit ids;
- all ADDED new unit ids.

UNCHANGED units must not be requested for re-extraction.

## 5. Safe full-reextract fallback

If exact alignment is insufficient to safely carry forward prior assertions, do not guess.

Define:
DeltaMode:
- DELTA_SAFE
- FULL_REEXTRACT_REQUIRED
- REVIEW_REQUIRED

Examples requiring FULL_REEXTRACT_REQUIRED:
- prior assertion inventory references a prior unit that cannot be resolved safely into the new version while the assertion would otherwise need carrying;
- upstream manifest explicitly declares segmentation/identity reset;
- duplicate/ambiguous cross-version alignment prevents deterministic carry-forward but does not indicate malicious conflict.

Hard structural contradictions use REVIEW_REQUIRED/fail-closed as appropriate.

When FULL_REEXTRACT_REQUIRED:
- extraction scope = all new units;
- do not pretend docs/03 changed-only optimization was achieved;
- diagnostics explain why.

## 6. DeltaExtractionRequest

Produce an internal request object for the upstream extractor, not the extraction itself.

At least:
- work_id;
- prior_source_version_id;
- new_source_version_id;
- new_ref_id;
- extraction_unit_ids;
- requested locators;
- reason;
- trace_id/provenance_id.

For PREPRINT_TO_JOURNAL + DELTA_SAFE:
reason = changed_or_added_units_only.

No network or LLM call in core.

## 7. Assertion inventories with content-unit binding

Do not change public Assertion schema.

Add INTERNAL wrappers:

### VersionAssertionInventory
- source_version_id;
- ref_id;
- assertions;
- assertion_unit_map: assertion_id -> unit_id.

### DeltaAssertionBatch
- source_version_id;
- ref_id;
- assertions;
- assertion_unit_map.

Validation:
- every assertion id unique;
- every mapped unit exists in its manifest;
- delta batch assertions may refer only to extraction_unit_ids;
- assertion.ref_id must match the batch/new ref_id;
- no assertion may claim an UNCHANGED unit in DELTA_SAFE mode.

## 8. Carry forward unchanged assertions safely

For UNCHANGED aligned units:
- prior content hash == new content hash;
- carry forward the prior assertion semantics without re-extraction.

Create a NEW assertion for the new source version, not a mutable alias of the old assertion.

Required deterministic transformation:
- new ref_id = target/new ref_id;
- new assertion id deterministic from:
  prior assertion id + new source_version_id + new unit_id;
- semantic subject/property/object/conditions/claim_type/origin/confidence/quality preserved;
- provenance sentence may be preserved because content hash is identical;
- provenance locator MUST use the new unit locator.

Do not mutate the prior Assertion object.

Record lineage:
old_assertion_id -> carried_assertion_id.

## 9. Build complete target AssertionSet

For DELTA_SAFE:
target assertions =
- carried-forward assertions from UNCHANGED units;
- upstream delta-extracted assertions from MODIFIED/ADDED units.

REMOVED prior-unit assertions are not carried.

For FULL_REEXTRACT_REQUIRED:
- require upstream batch for all new units;
- no prior assertion carry-forward;
- target assertions come from the full new extraction.

Target AssertionSet:
- ref_id = new ref_id;
- metadata supplied for new source version;
- normal AssertionSet validation remains applicable.

This target set is intended for existing KnowledgeCurator + DocumentCommitCoordinator in a later publication step.

## 10. Deterministic assertion transition diff

Need map PRIOR assertions to TARGET assertions for lifecycle actions.

First partition by content-unit relationship.

### Unchanged units
Every carried assertion has explicit lineage:
old -> carried-new
=> supersede action.

### Removed units
All prior assertions bound to removed units:
=> archive action.

### Modified units
Compare old assertions in prior unit against new assertions in aligned new unit using a deterministic semantic slot key.

Recommended semantic slot key excludes value and locator, and includes:
- subject.eddo_class;
- subject.resolved_entity;
- property;
- normalized conditions tuple;
- claim_type;
- value_type where needed to avoid category collision.

Do NOT use LLM/fuzzy text.

Rules:
- unique old slot + unique new slot:
  - if full semantic payload equal except source/provenance identity -> supersede old -> new as version replacement;
  - if value/unit/uncertainty/etc changed -> supersede old -> new;
- old slot with no new match -> archive old;
- new slot with no old match -> added assertion, no old supersede;
- multiple old or multiple new assertions with same slot => REVIEW_REQUIRED for that unit; no automatic lifecycle draft.

## 11. Full semantic assertion hash

Implement a deterministic internal semantic payload/hash suitable for comparing assertions.

Include:
- subject class/entity;
- property;
- object value/unit/value_type/uncertainty;
- normalized conditions;
- claim_type;
- source_claim_origin;
- relevant scientific flags if material.

Exclude:
- assertion id;
- ref_id;
- provenance locator;
- trace-only fields.

Do not redefine the existing §5 commit hash; this is an internal delta comparison function.

## 12. RevisionPackage

Produce an INTERNAL RevisionPackage containing at least:
- work_id;
- prior_source_version_id;
- new_source_version_id;
- relation;
- prior_ref_id;
- new_ref_id;
- prior_bound_kb_version_id;
- content_delta;
- target_assertion_set;
- supersede_actions: old assertion id -> new assertion id;
- archive_actions;
- added_assertion_ids;
- extraction evidence/diagnostics;
- requires_manual_review;
- trace_id/provenance_id.

For PREPRINT_TO_JOURNAL:
- lifecycle reason = PREPRINT_TO_JOURNAL.

## 13. Build frozen Lifecycle RevisionDraft, but do not publish yet

Add a pure adapter/helper:
RevisionPackage -> RevisionDraft

It must populate:
- trigger=LifecycleReason.PREPRINT_TO_JOURNAL (or mapped supported relation);
- affected_assertion_ids;
- supersede_actions;
- archive_actions;
- replacement_assertion_ids;
- evidence_refs;
- trace/provenance;
- rationale.

Important:
The final lifecycle base_version_id cannot be safely frozen before target new-version commit advances the current KB version.

Therefore Phase 5.2 draft/package should carry:
- prior_bound_kb_version_id for validation/audit;
- base_version_id unresolved or explicitly marked publication-time.

Do NOT call apply_revision() in Phase 5.2.

Publication orchestration will bind the actual current target commit version as lifecycle base in the next phase.

## 14. Risk gate

Do not fabricate:
high_confidence / multi_source / no_controversy.

RevisionPackage may carry review metadata supplied by the caller.

If deterministic assertion matching is ambiguous:
- requires_manual_review=true;
- do not output an auto-publishable lifecycle draft.

Do not bypass frozen evaluate_risk_gate.

## 15. VersionUpgradeIntent validation

Before delta planning:
- intent work/prior/new source versions must exist in SourceVersionRegistry;
- both versions belong to intent.work_id;
- new.prior_source_version_id == prior.source_version_id;
- relation matches records;
- for P2J prior PREPRINT / new JOURNAL;
- prior should have a bound KB version if lifecycle upgrade is being prepared.

Contradiction => fail closed.

## 16. Idempotency

Same:
- VersionUpgradeIntent;
- prior/new manifests;
- assertion inventories/batches

must produce the same:
- ContentDeltaPlan;
- carried assertion ids;
- AssertionTransition diff;
- RevisionPackage id.

Use canonical deterministic hashes/ids.

No random UUIDs in delta/revision package identity.

## 17. Tests

Maintain:
- knowledge_curator >= 421 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:

### content delta
1. same unit id + same hash -> unchanged;
2. explicit prior_unit_id + same hash -> unchanged;
3. aligned hash changed -> modified;
4. new unaligned unit -> added;
5. prior unaligned unit -> removed;
6. duplicate prior alignment -> fail closed;
7. missing explicit prior_unit_id -> fail closed;
8. unsafe alignment/inventory -> FULL_REEXTRACT_REQUIRED.

### extraction scope
9. DELTA_SAFE requests only modified+added units;
10. unchanged unit is never requested;
11. full fallback requests all new units;
12. delta batch containing unchanged unit -> reject.

### carry-forward
13. unchanged assertion cloned with deterministic new id;
14. prior object remains unmodified;
15. new ref_id/new locator applied;
16. semantic payload preserved.

### assertion transitions
17. unchanged carried old->new supersede;
18. modified unique slot old->new supersede;
19. removed old assertion -> archive;
20. newly added assertion -> added only;
21. ambiguous duplicate semantic slot -> review required.

### upgrade package
22. invalid source-version lineage -> reject;
23. P2J package has correct lifecycle reason;
24. deterministic replay yields same package id;
25. RevisionDraft contains exact supersede/archive actions;
26. Phase 5.2 does not call LifecycleRevisionCoordinator.apply_revision.

## 18. CONTRACT_GAPS

Keep CG-019.
Add/maintain CG-020 for upstream stable content-unit/alignment schema.

Do not invent a public parser contract.

## 19. Deliverable

Create:
results/phase-05-2-executor-report.md

Report:
- exact content-unit alignment: PASS/FAILED;
- delta classification: PASS/FAILED;
- safe full-reextract fallback: PASS/FAILED;
- delta extraction request: PASS/FAILED;
- unchanged assertion carry-forward: PASS/FAILED;
- assertion transition diff: PASS/FAILED;
- ambiguity review gate: PASS/FAILED;
- RevisionPackage determinism: PASS/FAILED;
- lifecycle draft generation: PASS/FAILED;
- lifecycle publication performed: NO;
- integration tests;
- knowledge_curator tests;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 20. Completion

Update status.json:
- phase = 5.2
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-2-executor-report.md

Push main and STOP.

Do not start publication orchestration / Phase 5.3 until Planner review.
