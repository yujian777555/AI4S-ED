# Phase 4.1.3 Executor Report — Tokenizer Window & Coarse Diagnostics

**Executor:** MiMo  
**Date:** 2026-09-29  
**Phase:** 4.1.3

---

## 1. Tokenizer-driven windows

`chunk_text` 删除 `str.split()` windowing。完整流程：`tokenizer.encode(text)` → slice encoded tokens → `tokenizer.decode(window)`。overlap_tokens 针对 encoded token sequence。

## 2. Format preservation

测试验证 `"a  b   c"` 切入同一 chunk 后保留多空格；换行保留；中文/non-ASCII 保留。

## 3. Token overlap semantics

相邻 body window 最后 64 encoded tokens == 下一 window 前 64 encoded tokens。prefix 不计入 overlap。

## 4. Full payload token budget

`tokenizer.count(full_payload) <= max_tokens` 持续有效。超出时缩小 encoded window（不退回 word split）。

## 5. Coarse backend diagnostics

| 场景 | coarse_backend_present | coarse_status |
|---|---|---|
| 无 vector/keyword port | false | COARSE_ABSENT |
| 有 port + 0 hits | **true** | **COARSE_ZERO** |
| 有 port + hits | true | COARSE_HIT |

新增：`coarse_channels_attempted` / `coarse_channels_with_hits` / `coarse_fused_hit_count`。

## 6. Fallback consistency

ABSENT/ZERO + fallback=false → 0 fine hits  
ABSENT/ZERO + fallback=true → explicit fine fallback  
语义不变。

## 7. Test counts

```text
knowledge_curator: 243 passed / 0 failed  (228 + 15 新)
integration/dsh:   70 passed / 0 failed
```

## 8. Public contracts changed?

**NO**

## 9. CONTRACT_GAPS

**无新增**

## 10. Implementation SHA

```
implementation commit: <pending>
```
