"""FlagEmbedding / transformers compatibility shims (Phase 4.2.2).

Two environment issues on this machine (transformers 4.49 + FlagEmbedding 1.4.2):

1. `transformers.models.xlm_roberta.tokenization_xlm_roberta` crashes (0xC0000005)
   when imported through transformers' _LazyModule. Preload the module with a
   manual loader after importing its deps.

2. FlagEmbedding 1.4.2 passes `dtype=` to `AutoModel.from_pretrained`, but
   transformers 4.49 forwards unknown kwargs to `cls(config, ...)` where the
   model rejects `dtype`. Translate `dtype=` -> `torch_dtype=` at the
   `from_pretrained` boundary.

Call `ensure_flagembedding_compat()` once before constructing BGEM3FlagModel /
FlagReranker.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any

_XLM_MOD = "transformers.models.xlm_roberta.tokenization_xlm_roberta"
_PKG = "transformers.models.xlm_roberta"


def _preload_xlm_roberta_tokenizer() -> None:
    if _XLM_MOD in sys.modules:
        return

    # Import deps first; the crash happens when they load together via lazy import.
    import sentencepiece  # noqa: F401
    from transformers.tokenization_utils import (  # noqa: F401
        AddedToken,
        PreTrainedTokenizer,
    )
    from transformers.utils import logging as _logging  # noqa: F401

    import transformers
    import transformers.models  # noqa: F401

    # Derive the package directory without importing transformers.models.xlm_roberta
    # (that lazy import is what triggers the crash).
    from pathlib import Path

    dir_path = str(Path(transformers.__file__).parent / "models" / "xlm_roberta")
    if not Path(dir_path).is_dir():
        raise RuntimeError(f"xlm_roberta package dir not found: {dir_path}")

    if _PKG not in sys.modules or not hasattr(sys.modules[_PKG], "__path__"):
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [dir_path]
        pkg.__package__ = "transformers.models"
        sys.modules[_PKG] = pkg

    tok_file = f"{dir_path}/tokenization_xlm_roberta.py"
    spec = importlib.util.spec_from_file_location(
        _XLM_MOD, tok_file, submodule_search_locations=[]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load tokenizer module from {tok_file}")
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    sys.modules[_XLM_MOD] = mod
    spec.loader.exec_module(mod)


def _patch_auto_model_dtype() -> None:
    """Translate FlagEmbedding's dtype= kwarg to torch_dtype= for transformers 4.49."""
    from transformers import (
        AutoModel,
        AutoModelForSequenceClassification,
        AutoModelForCausalLM,
    )

    targets = (
        AutoModel,
        AutoModelForSequenceClassification,
        AutoModelForCausalLM,
    )
    for target in targets:
        if getattr(target.from_pretrained, "_kc_dtype_patched", False):
            continue
        original = target.from_pretrained.__func__  # type: ignore[attr-defined]

        def from_pretrained_compat(cls, *args: Any, __original=original, **kwargs: Any):
            if "dtype" in kwargs and "torch_dtype" not in kwargs:
                kwargs["torch_dtype"] = kwargs.pop("dtype")
            elif "dtype" in kwargs:
                kwargs.pop("dtype")
            return __original(cls, *args, **kwargs)

        from_pretrained_compat._kc_dtype_patched = True  # type: ignore[attr-defined]
        target.from_pretrained = classmethod(from_pretrained_compat)  # type: ignore[method-assign]


def ensure_flagembedding_compat() -> None:
    """Idempotent: safe to call multiple times."""
    _preload_xlm_roberta_tokenizer()
    _patch_auto_model_dtype()
