# Phase 5.1 Plan — §7.1 Incremental Intake Identity & Source-Version Family Registry

Planner: ChatGPT
Executor: Kimi/Codex
State: READY_FOR_EXECUTOR

## 0. Goal

Implement the knowledge_curator-owned identity/version-comparison gate for docs/03 §7.1.

Given an already-discovered source candidate from upstream, deterministically classify it as:
- EXACT_REPLAY;
- SAME_WORK_NEW_VERSION;
- NEW_WORK;
- REVIEW_REQUIRED / IDENTITY_CONFLICT.

Record append-only work/version lineage so preprint and journal versions can belong to one work family.

This phase does NOT discover literature.

## 1. Boundaries

Do NOT:
- crawl Crossref, arXiv, journal TOCs, RetractionWatch, publisher sites or citation networks;
- implement lit_researcher;
- implement fuzzy semantic title/author matching;
- automatically claim a preprint and journal article are the same work from embedding similarity;
- re-extract changed paragraphs yet;
- archive/supersede preprint assertions yet;
- change Phase 5.0 lifecycle semantics;
- add external event transport;
- create a public cross-team schema.

CG-019 remains an internal compatibility boundary.

## 2. Internal source identity models

Add INTERNAL temporary models, recommended:
knowledge_curator/schemas/source_versions.py

Recommended enums:

SourceKind:
- PREPRINT
- JOURNAL
- CONFERENCE
- STANDARD
- PATENT
- OTHER

IntakeDisposition:
- EXACT_REPLAY
- SAME_WORK_NEW_VERSION
- NEW_WORK
- REVIEW_REQUIRED
- IDENTITY_CONFLICT

VersionRelation:
- REVISION_OF
- PREPRINT_TO_JOURNAL
- CORRECTED_VERSION
- EXPLICIT_SAME_WORK
- NONE

Models should include at least:

SourceCandidate:
- ref_id;
- source_fingerprint;
- DocumentMetadata-compatible title/authors/year/source/doi/stable_id;
- source_kind;
- explicit_work_id optional;
- explicit_prior_version_id optional;
- explicit_relation optional;
- trace_id;
- provenance_id.

WorkRecord:
- work_id;
- created identity evidence;
- version ids / append order or equivalent append-only representation.

SourceVersionRecord:
- source_version_id;
- work_id;
- ref_id;
- source_fingerprint;
- normalized identifier evidence;
- source_kind;
- relation;
- prior_source_version_id optional;
- kb_version_id optional;
- snapshot_id optional;
- trace_id/provenance_id;
- append sequence.

Do not overload ref_id as the work-family identity.

## 3. Deterministic normalization

Implement small pure functions.

### DOI
Canonicalize only safe syntax:
- trim whitespace;
- remove leading doi:;
- remove https://doi.org/ or http://doi.org/ or http(s)://dx.doi.org/ prefix;
- casefold.

Do not fuzzy-correct malformed DOI strings.

### title
For matching only:
- Unicode NFKC;
- trim;
- collapse repeated whitespace;
- casefold.

Do NOT remove all punctuation or words.
Do NOT use embeddings/edit distance in Phase 5.1.

### stable_id
Trim surrounding whitespace.
Do not invent provider-specific normalization rules unless the provider namespace is explicit.

Preserve raw metadata alongside normalized match keys.

## 4. SourceVersionRegistry Port

Create an INTERNAL Port with operations sufficient for:
- lookup exact ref_id + fingerprint;
- lookup by normalized DOI;
- lookup by stable_id;
- lookup by normalized exact title;
- get work(work_id);
- get source version(source_version_id);
- list versions(work_id);
- append/register a prepared source version;
- bind source version to published kb_version_id + snapshot_id.

In-memory adapter required.

Registry is append-only for source version records.
A binding from unbound -> one published KB version may be a finalization field.
It may never be rebound to a different KB version.

## 5. Material idempotency

Same deterministic source_version_id + identical material:
- idempotent.

Same source_version_id + different material:
- fail closed.

Material identity includes at least:
- work_id;
- ref_id;
- fingerprint;
- normalized DOI/title/stable id;
- source kind;
- relation;
- prior version;
- trace/provenance where identity policy treats them as semantic.

Do not silently merge conflicting DOI/work mappings.

## 6. Classification precedence

Implement deterministic classification in this order.

### A. exact replay
If the same registered ref_id + source_fingerprint already exists:
- EXACT_REPLAY;
- return existing work/version binding;
- no new source version record.

### B. explicit lineage
If explicit_work_id / explicit_prior_version_id is supplied:
- target must exist;
- explicit prior must belong to explicit work;
- explicit relation must be compatible;
- candidate identifiers must not contradict a known exact DOI mapping to another work.

If valid and fingerprint is new:
- SAME_WORK_NEW_VERSION.

If contradictory:
- IDENTITY_CONFLICT.

### C. exact DOI
If normalized DOI maps to exactly one work:
- same fingerprint -> replay if applicable;
- different fingerprint -> SAME_WORK_NEW_VERSION.

If one DOI maps to multiple works:
- registry invariant error / IDENTITY_CONFLICT.

### D. stable_id
Same rule as exact stable id.

### E. exact normalized title only
A title-only hit is NOT enough to auto-merge in Phase 5.1.

Return REVIEW_REQUIRED with candidate work ids/evidence.

This avoids false merges for generic titles.

### F. no match
NEW_WORK.

## 7. DOI/title disagreement

Fail closed or review-required when identifiers disagree.

Examples:
- exact DOI -> Work A, explicit_work_id -> Work B: IDENTITY_CONFLICT;
- title -> Work A but DOI is new/unseen: do not silently merge from title alone;
- DOI exact Work A but title changed: DOI identity wins for same-work classification, but record title_changed diagnostic.

Do not rewrite historical metadata.

## 8. Work/version registration flow

Add an IncrementalIntakeService (name may vary):

prepare(candidate) -> IntakeDecision

Decision includes:
- disposition;
- work_id if resolved;
- existing source_version_id if replay;
- match evidence;
- ambiguity candidates;
- diagnostics;
- whether normal curation/commit should proceed.

For NEW_WORK / SAME_WORK_NEW_VERSION:
- create a deterministic prepared source version record only when caller explicitly proceeds;
- do not mark it published yet.

For REVIEW_REQUIRED / IDENTITY_CONFLICT:
- no source version publication/binding.

## 9. Bind only after successful KB publication

Add finalize/bind operation taking:
- prepared source_version_id;
- CommitResult or explicit kb_version_id + snapshot_id.

Allowed:
- CommitStatus.PUBLISHED;
- CommitStatus.IDEMPOTENT_HIT when binding matches the existing published source version.

Not allowed:
- FAILED;
- NOT_PUBLISHABLE;
- PENDING_VECTOR;
- PENDING_FINALIZE without confirmed published version binding.

If commit publishes and registry bind fails, retry must be idempotently recoverable.
Do not create a second source version.

## 10. Existing DocumentCommitCoordinator remains frozen

Do not rewrite its §5 commit algorithm.

Phase 5.1 composes around it:
source identity preflight
-> existing curator/commit path
-> source-version bind.

Exact same (ref_id, fingerprint) behavior remains compatible with the existing DocumentCommitStore idempotency.

## 11. Explicit preprint -> journal lineage

Phase 5.1 supports a caller-supplied explicit relation only.

Example:
- existing PREPRINT source version P1;
- candidate JOURNAL J1 with different ref_id/DOI;
- caller supplies explicit_work_id=P1.work_id, explicit_prior_version_id=P1, relation=PREPRINT_TO_JOURNAL.

Then:
- classify SAME_WORK_NEW_VERSION;
- register J1 into the same work;
- preserve P1;
- versions(work_id) shows both in append order.

Do NOT yet:
- archive P1 assertions;
- choose changed paragraphs;
- re-extract assertions;
- automatically infer the relation from title similarity.

Instead produce a structured follow-up:
IncrementalRevisionPlan / VersionUpgradeIntent containing:
- work_id;
- prior source version;
- new source version;
- relation=PREPRINT_TO_JOURNAL;
- base KB version if bound;
- requires_delta_extraction=true;
- lifecycle_reason=PREPRINT_TO_JOURNAL.

This is input for Phase 5.2.

## 12. New fingerprint under same DOI

Required scenario:
- DOI X / fingerprint F1 bound to KB V1;
- same DOI X / fingerprint F2 arrives.

Classify:
SAME_WORK_NEW_VERSION.

After successful existing curation/commit:
- append source version V2 to same work;
- preserve V1;
- bind V2 to the new KB version.

Do not treat different fingerprint as exact replay.

## 13. Same fingerprint under conflicting metadata

If the same ref_id+fingerprint arrives with materially contradictory identity metadata:
- fail closed / IDENTITY_CONFLICT;
- do not call it replay.

Add a material metadata check to replay classification.

## 14. Registry queries

Provide internal read helpers:
- resolve_work_by_version;
- list_versions(work_id);
- current/latest bound version according to append order;
- find_by_doi/stable_id/title.

Do not expose a mutable “delete version”.

## 15. Auditability

Every decision should report match evidence such as:
- exact_ref_fingerprint;
- exact_doi;
- exact_stable_id;
- exact_title_review_only;
- explicit_lineage.

Preserve trace_id + provenance_id.

Do not output opaque “matched=true” only.

## 16. Tests

Maintain:
- knowledge_curator >= 358 passed / 0 failed;
- integration/dsh >= 90 passed / 0 failed.

Add at least:

1. exact ref+fingerprint replay;
2. replay with contradictory metadata fails closed;
3. same DOI + new fingerprint -> SAME_WORK_NEW_VERSION;
4. exact stable_id + new fingerprint -> SAME_WORK_NEW_VERSION;
5. exact title only -> REVIEW_REQUIRED, not auto-merge;
6. no match -> NEW_WORK;
7. DOI maps to Work A + explicit Work B -> IDENTITY_CONFLICT;
8. invalid explicit prior/work lineage rejected;
9. explicit preprint -> journal relation merges versions into one work;
10. no fuzzy preprint merge without explicit relation;
11. bind only after published commit;
12. PENDING_VECTOR/PENDING_FINALIZE not falsely finalized;
13. bind retry idempotent;
14. conflicting rebind rejected;
15. list_versions preserves append-only lineage;
16. normalized DOI variants match safely;
17. NFKC/case/whitespace title normalization behaves deterministically;
18. different punctuation titles are not collapsed accidentally.

## 17. Deliverables

Create:
results/phase-05-1-executor-report.md

Report:
- normalization: PASS/FAILED;
- SourceVersionRegistry: PASS/FAILED;
- exact replay: PASS/FAILED;
- same-work new version: PASS/FAILED;
- title-only review gate: PASS/FAILED;
- identity conflict fail-closed: PASS/FAILED;
- published-bind idempotency: PASS/FAILED;
- explicit preprint->journal lineage: PASS/FAILED;
- upgrade intent generation: PASS/FAILED;
- exact test counts;
- public contracts changed: NO;
- implementation CODE SHA;
- origin/main SHA;
- CONTRACT_GAPS changes.

## 18. Completion

Update status.json:
- phase = 5.1
- actor = executor
- state = executor_complete
- latest_commit = actual CODE SHA
- result_expected = results/phase-05-1-executor-report.md

Push main and STOP.

Do not start Phase 5.2, crawlers, changed-paragraph extraction, or automatic fuzzy linkage until Planner review.
