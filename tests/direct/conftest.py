"""
Windows compatibility shim + LLM mock fix for gltest direct-mode.

1. gltest's direct loader duplicates a temp file onto fd 0 and then
   os.unlink()s it. On POSIX that is fine (the open fd keeps the data);
   on Windows os.unlink refuses to remove a file any handle still holds,
   raising PermissionError (WinError 32) on every direct deploy. This is
   an upstream test-library quirk, not a contract bug -- swallow exactly
   that failure so collection can proceed.

2. gltest's LLM mock auto-json-decodes a mock_llm() response and returns a
   dict. Solvent calls plain gl.nondet.exec_prompt(prompt) with no
   response_format and json.loads()es the returned TEXT itself, so it must
   receive the literal string. Patch _handle_llm_request to keep it.
"""

import os

_original_unlink = os.unlink


def _tolerant_unlink(path, *args, **kwargs):
    try:
        _original_unlink(path, *args, **kwargs)
    except PermissionError:
        pass


os.unlink = _tolerant_unlink

from gltest.direct import wasi_mock as _wasi_mock  # noqa: E402

_original_handle_llm_request = _wasi_mock._handle_llm_request


def _patched_handle_llm_request(vm, data):
    prompt = data.get("prompt", "")
    response = vm._match_llm_mock(prompt)
    if response is not None:
        return {"ok": response}
    return _original_handle_llm_request(vm, data)


_wasi_mock._handle_llm_request = _patched_handle_llm_request
