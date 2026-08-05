"""Azure OpenAI chat output-budget kwarg: detect-and-retry with process cache.

Deployment names are operator-chosen free text — do NOT decide
``max_tokens`` vs ``max_completion_tokens`` by substring-matching the
deployment string. Instead:

1. Optional env override ``AZURE_OPENAI_TOKEN_PARAM`` skips detection.
2. Otherwise try ``max_completion_tokens`` first (correct for current /
   GPT-5.x / o-series deployments).
3. On the specific Azure 400 ``unsupported_parameter`` for that token
   budget kwarg, retry once with the other kwarg.
4. Cache the working kwarg per deployment for the process lifetime.

(gpt-5 / gpt-4 family names are a useful comment/hint only — never the
decision mechanism.)
"""

from __future__ import annotations

import os
from typing import Any, Callable, TypeVar

PARAM_MAX_COMPLETION_TOKENS = "max_completion_tokens"
PARAM_MAX_TOKENS = "max_tokens"
TOKEN_PARAM_ENV = "AZURE_OPENAI_TOKEN_PARAM"
_TOKEN_PARAMS = (PARAM_MAX_COMPLETION_TOKENS, PARAM_MAX_TOKENS)
_DEFAULT_FIRST_PARAM = PARAM_MAX_COMPLETION_TOKENS

# deployment name -> winning token-budget kwarg name
_cache: dict[str, str] = {}

T = TypeVar("T")


def clear_output_token_param_cache() -> None:
    """Clear the process-lifetime cache (tests / forced re-detect)."""
    _cache.clear()


def cached_output_token_param(deployment: str) -> str | None:
    """Return the cached kwarg name for ``deployment``, if any."""
    key = (deployment or "").strip()
    return _cache.get(key)


def resolve_token_param_override() -> str | None:
    """Return a valid ``AZURE_OPENAI_TOKEN_PARAM`` override, or None."""
    raw = (os.environ.get(TOKEN_PARAM_ENV) or "").strip()
    if not raw:
        return None
    if raw in _TOKEN_PARAMS:
        return raw
    raise ValueError(
        f"{TOKEN_PARAM_ENV} must be one of {_TOKEN_PARAMS}, got {raw!r}"
    )


def is_unsupported_token_param_error(exc: BaseException) -> bool:
    """True only for Azure/OpenAI 400 unsupported-parameter on a token-budget kwarg.

    Matches the real API shape::

        Error code: 400 - {'error': {
            'message': \"Unsupported parameter: 'max_tokens' is not supported ...\",
            'type': 'invalid_request_error',
            'param': 'max_tokens',
            'code': 'unsupported_parameter',
        }}

    Other 400s (auth, context length, content filter, etc.) must NOT trigger
    a token-kwarg flip.
    """
    status = getattr(exc, "status_code", None)
    if status is not None and int(status) != 400:
        return False

    code = str(getattr(exc, "code", "") or "").lower()
    param = str(getattr(exc, "param", "") or "").lower()
    message = str(exc).lower()

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(err, dict):
            code = code or str(err.get("code") or "").lower()
            param = param or str(err.get("param") or "").lower()
            message = message or str(err.get("message") or "").lower()

    unsupported = (
        code == "unsupported_parameter"
        or "unsupported parameter" in message
    )
    if not unsupported:
        return False

    token_param_named = param in _TOKEN_PARAMS or any(p in message for p in _TOKEN_PARAMS)
    if not token_param_named:
        return False

    # If status_code is missing (string-only errors), still accept when the
    # message clearly names unsupported_parameter + a token budget kwarg.
    if status is None and "400" not in message and code != "unsupported_parameter":
        # Require explicit code when we cannot see HTTP 400.
        if "unsupported parameter" not in message:
            return False

    return True


def _other_param(param: str) -> str:
    if param == PARAM_MAX_COMPLETION_TOKENS:
        return PARAM_MAX_TOKENS
    return PARAM_MAX_COMPLETION_TOKENS


def _prefer_error(first: BaseException, second: BaseException) -> BaseException:
    """Prefer the more informative failure when both attempts fail."""
    first_flip = is_unsupported_token_param_error(first)
    second_flip = is_unsupported_token_param_error(second)
    if first_flip and not second_flip:
        return second
    if second_flip and not first_flip:
        return first
    if len(str(second)) >= len(str(first)):
        return second
    return first


def invoke_with_output_token_budget(
    create_fn: Callable[..., T],
    *,
    deployment: str,
    token_budget: int,
    **request_kwargs: Any,
) -> T:
    """Call ``create_fn`` with exactly one output-budget kwarg.

    ``request_kwargs`` must not already contain ``max_tokens`` or
    ``max_completion_tokens``. ``create_fn`` is invoked as
    ``create_fn(**{**request_kwargs, <param>: token_budget})``.

    Detection is try-once-retry on the known unsupported-parameter 400,
    then cached per ``deployment`` for the process lifetime. Set
    ``AZURE_OPENAI_TOKEN_PARAM`` to skip detection.
    """
    for banned in _TOKEN_PARAMS:
        if banned in request_kwargs:
            raise ValueError(
                f"request_kwargs must not include {banned!r}; "
                "invoke_with_output_token_budget adds the token budget kwarg"
            )

    dep = (deployment or "").strip() or "__default__"
    override = resolve_token_param_override()
    if override is not None:
        return create_fn(**{**request_kwargs, override: token_budget})

    cached = _cache.get(dep)
    if cached is not None:
        return create_fn(**{**request_kwargs, cached: token_budget})

    first_param = _DEFAULT_FIRST_PARAM
    second_param = _other_param(first_param)

    try:
        result = create_fn(**{**request_kwargs, first_param: token_budget})
    except Exception as first_exc:
        if not is_unsupported_token_param_error(first_exc):
            raise
        try:
            result = create_fn(**{**request_kwargs, second_param: token_budget})
        except Exception as second_exc:
            raise _prefer_error(first_exc, second_exc) from second_exc
        _cache[dep] = second_param
        return result

    _cache[dep] = first_param
    return result


__all__ = [
    "PARAM_MAX_COMPLETION_TOKENS",
    "PARAM_MAX_TOKENS",
    "TOKEN_PARAM_ENV",
    "cached_output_token_param",
    "clear_output_token_param_cache",
    "invoke_with_output_token_budget",
    "is_unsupported_token_param_error",
    "resolve_token_param_override",
]
