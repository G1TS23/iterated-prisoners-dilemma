"""Client LM Studio (SDK officiel `lmstudio`).

Repris de Trivial Pursuit : sortie structurée + repli automatique en texte
libre si le moteur refuse le schéma (observé avec certains modèles/backends,
ex. HTTP 400 "Failed to initialize samplers").
"""
from __future__ import annotations

import time


class LMStudio:
    def __init__(self, host: str):
        import lmstudio as lms
        self._lms = lms
        self._lms.configure_default_client(host.replace("http://", "").replace("https://", ""))
        self._model = None
        self._model_key = None

    def load(self, model_key: str) -> None:
        if self._model_key == model_key:
            return
        if self._model is not None:
            try:
                self._model.unload()
            except Exception:
                pass
        self._model = self._lms.llm(model_key)
        self._model_key = model_key
        try:                       # warm-up non mesuré
            self._model.respond("ok", config={"maxTokens": 1})
        except Exception:
            pass

    def ask(self, prompt: str, *, temperature: float, seed: int,
            max_tokens: int, json_schema: dict | None) -> tuple[str, float, dict]:
        cfg = {"temperature": temperature, "maxTokens": max_tokens, "seed": seed}

        def _call(schema):
            kwargs = {"config": cfg}
            if schema is not None:
                kwargs["response_format"] = schema
            t0 = time.perf_counter()
            res = self._model.respond(prompt, **kwargs)
            return res, time.perf_counter() - t0

        try:
            res, elapsed = _call(json_schema)
        except Exception:
            if json_schema is None:
                raise
            res, elapsed = _call(None)          # repli texte libre

        stats = {}
        raw_stats = getattr(res, "stats", None)
        if raw_stats is not None:
            for k in ("tokens_per_second", "time_to_first_token_sec", "total_time_sec"):
                v = getattr(raw_stats, k, None)
                if v is not None:
                    stats[k] = v
        return (res.content or "").strip(), elapsed, stats
