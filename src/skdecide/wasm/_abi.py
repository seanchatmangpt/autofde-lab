"""Canonical Chatman ecosystem WebAssembly boundary.

The package intentionally exposes a tiny, capability-free core-Wasm ABI.  A
component receives canonical JSON and returns canonical JSON plus a receipt.
It receives no WASI imports by default, so filesystem, network, clock, random,
and process authority must be introduced by an explicit future host policy.
"""

from __future__ import annotations

ABI_NAME = "chatman:ecosystem/library"
ABI_VERSION = "1.0.0"
REQUEST_SCHEMA = "chatman.ecosystem.invoke.v1"
RESPONSE_SCHEMA = "chatman.ecosystem.response.v1"

MEMORY_EXPORT = "memory"
ALLOC_EXPORT = "chatman_alloc"
DEALLOC_EXPORT = "chatman_dealloc"
INVOKE_EXPORT = "chatman_invoke"

# The WIT is embedded so it ships in every wheel without relying on non-Python
# package-data configuration. ``python -m skdecide.wasm.build --emit-contract``
# writes this exact source to disk for component toolchains.
WIT = f"""package chatman:ecosystem@{ABI_VERSION};

interface library {{
  record invocation {{
    operation: string,
    payload-json: list<u8>,
    authority-json: list<u8>,
  }}

  record receipt-bound-result {{
    status: string,
    output-json: list<u8>,
    receipt-json: list<u8>,
  }}

  invoke: func(request: invocation) -> result<receipt-bound-result, string>;
}}

world chatman-library {{
  export library;
}}
"""

CORE_ABI = {
    "memory": MEMORY_EXPORT,
    "alloc": ALLOC_EXPORT,
    "dealloc": DEALLOC_EXPORT,
    "invoke": INVOKE_EXPORT,
    "invoke_signature": "(request_ptr: i32, request_len: i32) -> packed_ptr_len: i64",
    "packed_result": "high_u32=response_ptr, low_u32=response_len",
}
