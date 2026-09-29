# Phase 4.1.2 Executor Report — Final Retrieval Contract Closure

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.1.2

---

## 1. Tokenizer contract

`WordTokenizer` 真正 lossless reversible：encode 返回 whitespace+非空白 runs，decode 用 `"".join` 精确还原。测试覆盖：multiple spaces / newlines / 中文 / punctuation / non-ASCII。

## 2. Full payload token budget

最终 `full_payload = prefix + " " + body` 必须满足 `tokenizer.count(full_payload) <= max_tokens`。boundary-sensitive tokenizer（组合后 token 数≠单独之和）安全 shrink body window。prefix 放不下 → fail clearly。

## 3. RRF best-rank duplicate handling

同 channel 同 chunk 取 `min(valid ranks)`，与输入顺序无关。测试 rank5→rank1 与 rank1→rank5 结果一致且使用 rank=1。rank<1 拒绝。

## 4. Global coarse fusion

coarse VECTOR + KEYWORD 先各自 search，再 RRF 融合，取全局 `coarse_top_k`，再得到 `allowed_ref_ids`。不是 vector topK + keyword topK 的并集。diagnostics 记录 coarse_channels_used / coarse_fused_hit_count。

## 5. coarse_top_k semantics

融合后的全局上限，不是每个 channel 各自 topK 之和。测试 coarse_top_k=2 限制 fine 结果。

## 6. Fallback consistency

coarse absent 和 coarse zero-hit 统一遵守 `allow_fine_fallback_without_coarse`：
- false → 0 hits，不 unrestricted fine
- true → fine fallback，diagnostics 明确记录

## 7. Provenance preservation

全链路保留 ref_id / locator / chunk_type。

## 8. Test counts

```text
knowledge_curator: 228 passed / 0 failed  (210 + 18 新)
integration/dsh:   70 passed / 0 failed
```

## 9. Public contracts changed?

**NO**

## 10. CONTRACT_GAPS

**无新增**

## 11. Implementation SHA

```
implementation commit: <pending>
```
