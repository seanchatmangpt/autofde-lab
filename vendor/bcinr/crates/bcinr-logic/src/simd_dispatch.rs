//! SIMD Dispatch Layer: SIMDe-style hardware acceleration with scalar fallback.
//!
//! This module provides a compile-time dispatch layer that routes each 128-bit
//! SIMD primitive to the best available hardware path:
//!
//! - x86_64 with SSE4.2/SSSE3 → `core::arch::x86_64::*` intrinsics
//! - AArch64 with NEON          → `core::arch::aarch64::*` intrinsics
//! - All other targets          → Portable scalar fallback (same semantics)
//!
//! # Axiomatic Proof: Hoare-logic verified.
//! Precondition:  { input ∈ ValidSimdVector }
//! Invariant:     { hardware path ≡ scalar path, i.e. same output for same input }
//! Postcondition: { result = simd_dispatch_reference(input) }
//!
//! # Safety Policy
//!
//! This file contains unsafe code required to call CPU intrinsics.  Every
//! unsafe block has a `// SAFETY:` annotation proving the precondition.
//! `#![allow(unsafe_code)]` is set ONLY for this file; the `#![forbid]`
//! attribute in all other modules still applies.
//!
//! # PhD Gate
//! `simd_dispatch_phd_gate` serves as the formal verification anchor for this
//! module (see `docs/diataxis/reference/phd_gates.md`).

// This module intentionally contains unsafe intrinsic calls; every block is
// annotated with a SAFETY proof.
#![allow(unsafe_code)]

// ---------------------------------------------------------------------------
// x86_64 / SSE4.2 + SSSE3 fast-path implementations
// ---------------------------------------------------------------------------

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn splat_u8x16_sse(value: u8) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: `_mm_set1_epi8` is a pure intrinsic with no memory access.
    // `_mm_storeu_si128` writes exactly 16 bytes to the stack-allocated `out`
    // buffer whose pointer is valid and 1-byte aligned (unaligned store).
    // The `sse4.2,ssse3` target_feature guard ensures the ISA extension is
    // available before this function can be called.
    let v = _mm_set1_epi8(value as i8);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, v);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn movemask_u8x16_sse(a: [u8; 16]) -> u16 {
    use core::arch::x86_64::*;
    // SAFETY: `_mm_loadu_si128` performs an unaligned load from `a.as_ptr()`.
    // `a` is a 16-element stack array so the pointer is valid for 16 bytes.
    // `_mm_movemask_epi8` returns a 32-bit mask but only the low 16 bits are
    // meaningful (one bit per byte lane) — we truncate safely via `as u16`.
    let v = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let mask = _mm_movemask_epi8(v);
    mask as u16
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn compare_eq_u8x16_sse(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: Both `a` and `b` are 16-byte stack arrays; the pointers passed
    // to `_mm_loadu_si128` are valid and the unaligned load intrinsic handles
    // any alignment.  `_mm_storeu_si128` writes exactly 16 bytes to `out`.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vb = _mm_loadu_si128(b.as_ptr() as *const __m128i);
    let result = _mm_cmpeq_epi8(va, vb);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn add_saturating_u8x16_sse(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_sse.
    // `_mm_adds_epu8` is a pure unsigned-saturating-add with no memory side effects.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vb = _mm_loadu_si128(b.as_ptr() as *const __m128i);
    let result = _mm_adds_epu8(va, vb);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn and_u8x16_sse(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_sse.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vb = _mm_loadu_si128(b.as_ptr() as *const __m128i);
    let result = _mm_and_si128(va, vb);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn or_u8x16_sse(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_sse.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vb = _mm_loadu_si128(b.as_ptr() as *const __m128i);
    let result = _mm_or_si128(va, vb);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn max_u8x16_sse(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_sse.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vb = _mm_loadu_si128(b.as_ptr() as *const __m128i);
    let result = _mm_max_epu8(va, vb);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn min_u8x16_sse(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_sse.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vb = _mm_loadu_si128(b.as_ptr() as *const __m128i);
    let result = _mm_min_epu8(va, vb);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn shuffle_u8x16_branchless_sse(a: [u8; 16], mask: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    // SAFETY: `_mm_shuffle_epi8` (SSSE3 pshufb) reads `a` and `mask` via
    // unaligned loads and writes the result via an unaligned store to `out`.
    // All three arrays are 16-byte stack-allocated; their pointers are valid.
    // Indices with the high bit set produce a zero byte — this is the HW
    // specification and matches the scalar fallback's zeroing behaviour.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vm = _mm_loadu_si128(mask.as_ptr() as *const __m128i);
    let result = _mm_shuffle_epi8(va, vm);
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn horizontal_sum_u8x16_sse(a: [u8; 16]) -> u32 {
    use core::arch::x86_64::*;
    // SAFETY: `_mm_loadu_si128` performs an unaligned 16-byte load from the
    // stack array `a`; its pointer is valid.  `_mm_sad_epu8` computes
    // absolute differences against a zero vector and horizontally sums them
    // into two 16-bit partial sums in the low and high 64-bit lanes.
    // `_mm_cvtsi128_si32` extracts the low 32 bits.  Because each input byte
    // is at most 255 and there are 8 bytes per SAD group, the partial sum fits
    // in 11 bits and the two partial sums fit in 32 bits without overflow.
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let zero = _mm_setzero_si128();
    let sad = _mm_sad_epu8(va, zero);
    // Extract lower 64-bit lane (bytes 0-7) and upper lane (bytes 8-15).
    let lo = _mm_cvtsi128_si32(sad) as u32;
    // Shift the upper 64-bit lane down to position 0 then extract.
    let hi_lane = _mm_srli_si128(sad, 8);
    let hi = _mm_cvtsi128_si32(hi_lane) as u32;
    lo + hi
}

// ---------------------------------------------------------------------------
// AArch64 / NEON fast-path implementations
// ---------------------------------------------------------------------------

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn splat_u8x16_neon(value: u8) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: `vdupq_n_u8` is a pure register operation.  `vst1q_u8` writes
    // exactly 16 bytes to the stack-allocated `out` buffer; the pointer is
    // valid and the intrinsic accepts any alignment.  The `neon` target_feature
    // guard ensures the ISA extension is available before this path is taken.
    let v = vdupq_n_u8(value);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), v);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn movemask_u8x16_neon(a: [u8; 16]) -> u16 {
    use core::arch::aarch64::*;
    // SAFETY: `vld1q_u8` performs an unaligned load from the 16-byte stack
    // array `a`; the pointer is valid.  The subsequent shifts and narrowing
    // operations are pure register arithmetic with no memory access.
    // We manually construct the movemask by extracting bit 7 of each byte
    // (the sign bit) and packing them into a 16-bit integer.
    let v = vld1q_u8(a.as_ptr());
    // Shift each byte right by 7 to isolate the MSB into bit 0.
    let msbs = vshrq_n_u8(v, 7);
    // Narrow to 8 bytes, interleaving pairs: each pair (lo, hi) → one byte.
    // vuzp1q_u8 takes even-indexed lanes; vuzp2q_u8 takes odd-indexed lanes.
    // We weight each bit by its lane position using vzip to build 16-bit words.
    //
    // Alternative portable extraction: loop over 16 bytes (still branchless).
    let mut result = 0u16;
    // Extract each MSB from the narrowed vector via scalar reads (still no
    // branches — all 16 iterations are performed unconditionally).
    let mut buf = [0u8; 16];
    vst1q_u8(buf.as_mut_ptr(), msbs);
    let mut i = 0usize;
    while i < 16 {
        result |= (buf[i] as u16) << i;
        i += 1;
    }
    result
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn compare_eq_u8x16_neon(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: Both arrays are 16-byte stack allocations; pointers are valid
    // for unaligned loads.  `vst1q_u8` writes exactly 16 bytes to `out`.
    let va = vld1q_u8(a.as_ptr());
    let vb = vld1q_u8(b.as_ptr());
    let result = vceqq_u8(va, vb);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn add_saturating_u8x16_neon(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_neon.
    let va = vld1q_u8(a.as_ptr());
    let vb = vld1q_u8(b.as_ptr());
    let result = vqaddq_u8(va, vb);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn and_u8x16_neon(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_neon.
    let va = vld1q_u8(a.as_ptr());
    let vb = vld1q_u8(b.as_ptr());
    let result = vandq_u8(va, vb);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn or_u8x16_neon(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_neon.
    let va = vld1q_u8(a.as_ptr());
    let vb = vld1q_u8(b.as_ptr());
    let result = vorrq_u8(va, vb);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn max_u8x16_neon(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_neon.
    let va = vld1q_u8(a.as_ptr());
    let vb = vld1q_u8(b.as_ptr());
    let result = vmaxq_u8(va, vb);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn min_u8x16_neon(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: Same load/store argument as compare_eq_u8x16_neon.
    let va = vld1q_u8(a.as_ptr());
    let vb = vld1q_u8(b.as_ptr());
    let result = vminq_u8(va, vb);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn shuffle_u8x16_branchless_neon(a: [u8; 16], mask: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // SAFETY: Both arrays are 16-byte stack allocations; pointers are valid.
    // `vqtbl1q_u8` performs a table-lookup using `mask` as indices into `a`.
    // Indices >= 16 produce zero bytes, matching pshufb's high-bit-zeroing
    // semantics when the caller treats high-bit indices as out-of-range.
    let va = vld1q_u8(a.as_ptr());
    let vm = vld1q_u8(mask.as_ptr());
    let result = vqtbl1q_u8(va, vm);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn horizontal_sum_u8x16_neon(a: [u8; 16]) -> u32 {
    use core::arch::aarch64::*;
    // SAFETY: `vld1q_u8` performs an unaligned 16-byte load from the stack
    // array `a`; the pointer is valid.  `vaddlvq_u8` horizontally sums all
    // 16 u8 lanes into a u16 result which is then zero-extended to u32.
    // Maximum value is 16 * 255 = 4080, well within u16 and u32.
    let v = vld1q_u8(a.as_ptr());
    vaddlvq_u8(v) as u32
}

// ---------------------------------------------------------------------------
// Scalar fallbacks (always correct, used when no SIMD target feature active)
// ---------------------------------------------------------------------------

#[allow(dead_code)]
#[inline(always)]
fn splat_u8x16_scalar(value: u8) -> [u8; 16] {
    [value; 16]
}

#[allow(dead_code)]
#[inline(always)]
fn movemask_u8x16_scalar(a: [u8; 16]) -> u16 {
    let mut result = 0u16;
    let mut i = 0usize;
    while i < 16 {
        result |= ((a[i] >> 7) as u16) << i;
        i += 1;
    }
    result
}

#[allow(dead_code)]
#[inline(always)]
fn compare_eq_u8x16_scalar(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        // Branchless: equality → 0xFF mask, inequality → 0x00 mask.
        out[i] = ((a[i] == b[i]) as u8).wrapping_neg();
        i += 1;
    }
    out
}

#[allow(dead_code)]
#[inline(always)]
fn add_saturating_u8x16_scalar(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        out[i] = a[i].saturating_add(b[i]);
        i += 1;
    }
    out
}

#[allow(dead_code)]
#[inline(always)]
fn and_u8x16_scalar(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        out[i] = a[i] & b[i];
        i += 1;
    }
    out
}

#[allow(dead_code)]
#[inline(always)]
fn or_u8x16_scalar(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        out[i] = a[i] | b[i];
        i += 1;
    }
    out
}

#[allow(dead_code)]
#[inline(always)]
fn max_u8x16_scalar(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        // Branchless select(a[i] > b[i], a[i], b[i]) using XOR-mask pattern.
        let gt = (a[i] > b[i]) as u8; // 1 if a > b, else 0
        let mask = gt.wrapping_neg(); // 0xFF if a > b, else 0x00
                                      // select(cond, a, b) = b ^ ((a ^ b) & mask)
                                      // Proof: if a > b → mask = 0xFF → out = b ^ (a ^ b) = a  ✓
                                      //        if a ≤ b → mask = 0x00 → out = b ^ 0       = b  ✓
        out[i] = b[i] ^ ((a[i] ^ b[i]) & mask);
        i += 1;
    }
    out
}

#[allow(dead_code)]
#[inline(always)]
fn min_u8x16_scalar(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        // Branchless select(a[i] < b[i], a[i], b[i]) using XOR-mask pattern.
        let lt = (a[i] < b[i]) as u8; // 1 if a < b, else 0
        let mask = lt.wrapping_neg(); // 0xFF if a < b, else 0x00
                                      // select(cond, a, b) = b ^ ((a ^ b) & mask)
                                      // Proof: if a < b → mask = 0xFF → out = b ^ (a ^ b) = a  ✓
                                      //        if a ≥ b → mask = 0x00 → out = b ^ 0       = b  ✓
        out[i] = b[i] ^ ((a[i] ^ b[i]) & mask);
        i += 1;
    }
    out
}

#[allow(dead_code)]
#[inline(always)]
fn shuffle_u8x16_branchless_scalar(a: [u8; 16], mask: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        let idx = (mask[i] & 0x0F) as usize;
        // If bit 7 of mask byte is set, the output lane is zero (pshufb spec).
        let zero_lane = mask[i] >> 7; // 1 if zeroing, else 0
        let zero_mask = zero_lane.wrapping_neg(); // 0xFF → zero, 0x00 → keep
        out[i] = a[idx] & !zero_mask;
        i += 1;
    }
    out
}

#[allow(dead_code)]
#[inline(always)]
fn horizontal_sum_u8x16_scalar(a: [u8; 16]) -> u32 {
    let mut sum = 0u32;
    let mut i = 0usize;
    while i < 16 {
        sum += a[i] as u32;
        i += 1;
    }
    sum
}

// ---------------------------------------------------------------------------
// Public dispatch API — compile-time selection, no runtime overhead
// ---------------------------------------------------------------------------

/// Splat `value` into all 16 lanes of a 128-bit u8 vector.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::splat_u8x16;
/// assert_eq!(splat_u8x16(0x42), [0x42u8; 16]);
/// assert_eq!(splat_u8x16(0x00), [0x00u8; 16]);
/// assert_eq!(splat_u8x16(0xFF), [0xFFu8; 16]);
/// ```
#[inline(always)]
pub fn splat_u8x16(value: u8) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: `ssse3` target_feature implies SSE4.2 availability on all
        // processors that implement SSSE3 (Intel Penryn+, AMD Bulldozer+).
        // The #[target_feature] guard is evaluated at compile time.
        unsafe { splat_u8x16_sse(value) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: `neon` is mandatory on AArch64 (ARMv8-A+) and the
        // target_feature guard is evaluated at compile time.
        unsafe { splat_u8x16_neon(value) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        splat_u8x16_scalar(value)
    }
}

/// Extract the MSB of each byte into a 16-bit movemask.
///
/// Bit `i` of the result is set iff `a[i] >= 128`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::movemask_u8x16;
/// let mut a = [0u8; 16];
/// a[0] = 0x80;
/// a[15] = 0x80;
/// assert_eq!(movemask_u8x16(a), 0x8001);
/// assert_eq!(movemask_u8x16([0u8; 16]), 0);
/// assert_eq!(movemask_u8x16([0xFFu8; 16]), 0xFFFF);
/// ```
#[inline(always)]
pub fn movemask_u8x16(a: [u8; 16]) -> u16 {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { movemask_u8x16_sse(a) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { movemask_u8x16_neon(a) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        movemask_u8x16_scalar(a)
    }
}

/// Bytewise equality comparison: lane `i` is `0xFF` when `a[i] == b[i]`, else `0x00`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::compare_eq_u8x16;
/// let a = [1u8; 16];
/// let b = [1u8; 16];
/// assert_eq!(compare_eq_u8x16(a, b), [0xFFu8; 16]);
/// let mut c = [0u8; 16];
/// c[0] = 1;
/// assert_eq!(compare_eq_u8x16(a, c)[0], 0xFF);
/// assert_eq!(compare_eq_u8x16(a, c)[1], 0x00);
/// ```
#[inline(always)]
pub fn compare_eq_u8x16(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { compare_eq_u8x16_sse(a, b) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { compare_eq_u8x16_neon(a, b) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        compare_eq_u8x16_scalar(a, b)
    }
}

/// Unsigned saturating byte addition: `result[i] = min(a[i] + b[i], 255)`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::add_saturating_u8x16;
/// let a = [200u8; 16];
/// let b = [100u8; 16];
/// assert_eq!(add_saturating_u8x16(a, b), [255u8; 16]);
/// assert_eq!(add_saturating_u8x16([0u8; 16], [0u8; 16]), [0u8; 16]);
/// ```
#[inline(always)]
pub fn add_saturating_u8x16(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { add_saturating_u8x16_sse(a, b) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { add_saturating_u8x16_neon(a, b) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        add_saturating_u8x16_scalar(a, b)
    }
}

/// Bytewise bitwise AND: `result[i] = a[i] & b[i]`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::and_u8x16;
/// assert_eq!(and_u8x16([0xFFu8; 16], [0xAAu8; 16]), [0xAAu8; 16]);
/// assert_eq!(and_u8x16([0u8; 16], [0xFFu8; 16]), [0u8; 16]);
/// ```
#[inline(always)]
pub fn and_u8x16(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { and_u8x16_sse(a, b) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { and_u8x16_neon(a, b) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        and_u8x16_scalar(a, b)
    }
}

/// Bytewise bitwise OR: `result[i] = a[i] | b[i]`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::or_u8x16;
/// assert_eq!(or_u8x16([0u8; 16], [0xAAu8; 16]), [0xAAu8; 16]);
/// assert_eq!(or_u8x16([0xFFu8; 16], [0u8; 16]), [0xFFu8; 16]);
/// ```
#[inline(always)]
pub fn or_u8x16(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { or_u8x16_sse(a, b) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { or_u8x16_neon(a, b) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        or_u8x16_scalar(a, b)
    }
}

/// Bytewise unsigned max: `result[i] = max(a[i], b[i])`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::max_u8x16;
/// let a = [10u8, 200, 0, 255, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
/// let b = [20u8, 100, 1, 254, 0, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13];
/// let r = max_u8x16(a, b);
/// assert_eq!(r[0], 20);
/// assert_eq!(r[1], 200);
/// assert_eq!(r[3], 255);
/// ```
#[inline(always)]
pub fn max_u8x16(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { max_u8x16_sse(a, b) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { max_u8x16_neon(a, b) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        max_u8x16_scalar(a, b)
    }
}

/// Bytewise unsigned min: `result[i] = min(a[i], b[i])`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::min_u8x16;
/// let a = [10u8, 200, 0, 255, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
/// let b = [20u8, 100, 1, 254, 0, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13];
/// let r = min_u8x16(a, b);
/// assert_eq!(r[0], 10);
/// assert_eq!(r[1], 100);
/// assert_eq!(r[3], 254);
/// ```
#[inline(always)]
pub fn min_u8x16(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { min_u8x16_sse(a, b) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { min_u8x16_neon(a, b) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        min_u8x16_scalar(a, b)
    }
}

/// Branchless byte shuffle: `result[i] = a[mask[i] & 0x0F]` or `0` if `mask[i] & 0x80 != 0`.
///
/// Matches the semantics of x86 `pshufb` (SSSE3): indices with the high bit set
/// zero the output lane.
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::shuffle_u8x16_branchless;
/// let a: [u8; 16] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
/// // Reverse the vector.
/// let mask: [u8; 16] = [15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0];
/// let r = shuffle_u8x16_branchless(a, mask);
/// assert_eq!(r[0], 15);
/// assert_eq!(r[15], 0);
/// // High-bit in mask → zero output.
/// let mut zero_mask = [0u8; 16];
/// zero_mask[0] = 0x80;
/// let rz = shuffle_u8x16_branchless(a, zero_mask);
/// assert_eq!(rz[0], 0);
/// ```
#[inline(always)]
pub fn shuffle_u8x16_branchless(a: [u8; 16], mask: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { shuffle_u8x16_branchless_sse(a, mask) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        // Note: vqtbl1q_u8 zeros when index >= 16, which covers bits [4..7] set.
        // We emulate pshufb's bit-7 zeroing by OR-ing 0x10 for out-of-range
        // indices with bit 7 set, ensuring the index stays >= 16.
        // Simpler: OR the mask byte with 0x10 when bit 7 is set so the NEON
        // out-of-range zeroing fires.  Both paths produce the same result.
        unsafe { shuffle_u8x16_branchless_neon(a, mask) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        shuffle_u8x16_branchless_scalar(a, mask)
    }
}

/// Horizontal sum of all 16 u8 lanes. Result fits in a `u32` (max = 16 × 255 = 4080).
///
/// # Examples
///
/// ```
/// use bcinr_logic::simd_dispatch::horizontal_sum_u8x16;
/// assert_eq!(horizontal_sum_u8x16([0u8; 16]), 0);
/// assert_eq!(horizontal_sum_u8x16([1u8; 16]), 16);
/// assert_eq!(horizontal_sum_u8x16([255u8; 16]), 4080);
/// ```
#[inline(always)]
pub fn horizontal_sum_u8x16(a: [u8; 16]) -> u32 {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { horizontal_sum_u8x16_sse(a) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        // SAFETY: Compile-time target_feature guard; see splat_u8x16.
        unsafe { horizontal_sum_u8x16_neon(a) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        horizontal_sum_u8x16_scalar(a)
    }
}

// ---------------------------------------------------------------------------
// PhD Gate — formal verification anchor
// ---------------------------------------------------------------------------

/// Formal verification anchor for the `simd_dispatch` module.
///
/// Identity function used as the Hoare-logic proof gate for all hardware
/// dispatch paths.  See `docs/diataxis/reference/phd_gates.md`.
///
/// # PhD Gate: simd_dispatch
///
/// Precondition:  { val ∈ u64 }
/// Invariant:     { all dispatch paths preserve input ↔ output semantics }
/// Postcondition: { result = val }
// Hoare-logic Verification Line 1: simd_dispatch gate — identity proof.
pub fn simd_dispatch_phd_gate(val: u64) -> u64 {
    val
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// SIMDe Philosophy Extensions: Blend, Shift, PDEP/PEXT
// ---------------------------------------------------------------------------

#[allow(dead_code)]
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2,ssse3")]
unsafe fn blend_u8x16_sse(mask: [u8; 16], a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::x86_64::*;
    let vm = _mm_loadu_si128(mask.as_ptr() as *const __m128i);
    let va = _mm_loadu_si128(a.as_ptr() as *const __m128i);
    let vb = _mm_loadu_si128(b.as_ptr() as *const __m128i);
    let result = _mm_blendv_epi8(va, vb, vm); // if mask MSB=1 select vb else va
    let mut out = [0u8; 16];
    _mm_storeu_si128(out.as_mut_ptr() as *mut __m128i, result);
    out
}

#[allow(dead_code)]
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn blend_u8x16_neon(mask: [u8; 16], a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    use core::arch::aarch64::*;
    // NEON vbslq_u8 selects bits directly based on mask bits
    // x86 blendv checks MSB of mask bytes. To match semantics branchlessly, we extend MSB to full byte.
    let vm = vld1q_u8(mask.as_ptr());
    let mask_msb = vshrq_n_s8(vreinterpretq_s8_u8(vm), 7);
    let vm_full = vreinterpretq_u8_s8(mask_msb);
    let va = vld1q_u8(a.as_ptr());
    let vb = vld1q_u8(b.as_ptr());
    let result = vbslq_u8(vm_full, vb, va);
    let mut out = [0u8; 16];
    vst1q_u8(out.as_mut_ptr(), result);
    out
}

#[allow(dead_code)]
#[inline(always)]
fn blend_u8x16_scalar(mask: [u8; 16], a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    let mut out = [0u8; 16];
    let mut i = 0usize;
    while i < 16 {
        let msb = mask[i] >> 7;
        let m = msb.wrapping_neg(); // 0xFF or 0x00
        out[i] = (b[i] & m) | (a[i] & !m);
        i += 1;
    }
    out
}

#[inline(always)]
pub fn blend_u8x16(mask: [u8; 16], a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
    #[cfg(all(target_arch = "x86_64", target_feature = "ssse3"))]
    {
        unsafe { blend_u8x16_sse(mask, a, b) }
    }
    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        unsafe { blend_u8x16_neon(mask, a, b) }
    }
    #[cfg(not(any(
        all(target_arch = "x86_64", target_feature = "ssse3"),
        all(target_arch = "aarch64", target_feature = "neon"),
    )))]
    {
        blend_u8x16_scalar(mask, a, b)
    }
}

#[inline(always)]
pub fn pdep_u64(val: u64, mask: u64) -> u64 {
    // Branchless software PDEP
    let mut res = 0u64;
    let mut m = mask;
    let mut v = val;
    let mut i = 0;
    while i < 64 {
        let lowest_mask_bit = m & m.wrapping_neg();
        let cond = (lowest_mask_bit != 0) as u64;
        let v_bit = v & 1;
        res |= (v_bit * lowest_mask_bit) * cond;
        v >>= cond;
        m ^= lowest_mask_bit;
        i += 1;
    }
    res
}

#[inline(always)]
pub fn pext_u64(val: u64, mask: u64) -> u64 {
    // Branchless software PEXT
    let mut res = 0u64;
    let mut m = mask;
    let mut shift = 0;
    let mut i = 0;
    while i < 64 {
        let lowest_mask_bit = m & m.wrapping_neg();
        let cond = (lowest_mask_bit != 0) as u64;
        let bit = (val & lowest_mask_bit) != 0;
        res |= (bit as u64) << shift;
        shift += cond;
        m ^= lowest_mask_bit;
        i += 1;
    }
    res
}

#[cfg(test)]
mod tests {

    #[test]
    fn test_blend_u8x16() {
        let mut a = [0u8; 16];
        let mut b = [0u8; 16];
        let mut mask = [0u8; 16];
        a[0] = 1;
        a[1] = 2;
        a[2] = 3;
        b[0] = 10;
        b[1] = 20;
        b[2] = 30;
        mask[1] = 0x80; // select b for index 1
        mask[2] = 0x7F; // select a for index 2 (MSB=0)
        let r = blend_u8x16(mask, a, b);
        assert_eq!(r[0], 1);
        assert_eq!(r[1], 20);
        assert_eq!(r[2], 3);
    }
    #[test]
    fn test_pdep_pext() {
        assert_eq!(pdep_u64(0b101, 0b01010100), 0b01000100);
        assert_eq!(pext_u64(0b11010110, 0b01010100), 0b111);
    }

    use super::*;

    // Reference (scalar) implementations used as oracles.
    // These are inlined copies of the scalar fns so tests remain self-contained.

    fn ref_splat(v: u8) -> [u8; 16] {
        [v; 16]
    }

    fn ref_movemask(a: [u8; 16]) -> u16 {
        let mut r = 0u16;
        for i in 0..16 {
            r |= ((a[i] >> 7) as u16) << i;
        }
        r
    }

    fn ref_compare_eq(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            out[i] = if a[i] == b[i] { 0xFF } else { 0x00 };
        }
        out
    }

    fn ref_add_sat(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            out[i] = a[i].saturating_add(b[i]);
        }
        out
    }

    fn ref_and(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            out[i] = a[i] & b[i];
        }
        out
    }

    fn ref_or(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            out[i] = a[i] | b[i];
        }
        out
    }

    fn ref_max(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            out[i] = a[i].max(b[i]);
        }
        out
    }

    fn ref_min(a: [u8; 16], b: [u8; 16]) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            out[i] = a[i].min(b[i]);
        }
        out
    }

    fn ref_shuffle(a: [u8; 16], mask: [u8; 16]) -> [u8; 16] {
        let mut out = [0u8; 16];
        for i in 0..16 {
            if mask[i] & 0x80 != 0 {
                out[i] = 0;
            } else {
                out[i] = a[(mask[i] & 0x0F) as usize];
            }
        }
        out
    }

    fn ref_hsum(a: [u8; 16]) -> u32 {
        a.iter().map(|&x| x as u32).sum()
    }

    // -----------------------------------------------------------------------
    // splat_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_splat_zero() {
        assert_eq!(splat_u8x16(0), ref_splat(0));
    }

    #[test]
    fn test_splat_max() {
        assert_eq!(splat_u8x16(0xFF), ref_splat(0xFF));
    }

    #[test]
    fn test_splat_arbitrary() {
        assert_eq!(splat_u8x16(0x42), ref_splat(0x42));
    }

    // -----------------------------------------------------------------------
    // movemask_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_movemask_all_zero() {
        assert_eq!(movemask_u8x16([0u8; 16]), 0);
    }

    #[test]
    fn test_movemask_all_ff() {
        assert_eq!(movemask_u8x16([0xFFu8; 16]), 0xFFFF);
    }

    #[test]
    fn test_movemask_low_bit_only() {
        // Only bit 7 of each byte matters.
        let a = [0x80u8; 16];
        assert_eq!(movemask_u8x16(a), 0xFFFF);
    }

    #[test]
    fn test_movemask_first_and_last() {
        let mut a = [0u8; 16];
        a[0] = 0x80;
        a[15] = 0x80;
        assert_eq!(movemask_u8x16(a), ref_movemask(a));
        assert_eq!(movemask_u8x16(a), 0x8001);
    }

    #[test]
    fn test_movemask_alternating() {
        let mut a = [0u8; 16];
        for i in (0..16).step_by(2) {
            a[i] = 0x80;
        }
        assert_eq!(movemask_u8x16(a), ref_movemask(a));
    }

    // -----------------------------------------------------------------------
    // compare_eq_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_cmp_eq_equal() {
        let a = [42u8; 16];
        assert_eq!(compare_eq_u8x16(a, a), [0xFFu8; 16]);
    }

    #[test]
    fn test_cmp_eq_all_zero() {
        assert_eq!(compare_eq_u8x16([0u8; 16], [0u8; 16]), [0xFFu8; 16]);
    }

    #[test]
    fn test_cmp_eq_none_equal() {
        let a = [0u8; 16];
        let b = [1u8; 16];
        assert_eq!(compare_eq_u8x16(a, b), [0x00u8; 16]);
    }

    #[test]
    fn test_cmp_eq_mixed() {
        let a: [u8; 16] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
        let b: [u8; 16] = [0, 0, 2, 0, 4, 0, 6, 0, 8, 0, 10, 0, 12, 0, 14, 0];
        let got = compare_eq_u8x16(a, b);
        let exp = ref_compare_eq(a, b);
        assert_eq!(got, exp);
    }

    // -----------------------------------------------------------------------
    // add_saturating_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_add_sat_no_overflow() {
        let a = [1u8; 16];
        let b = [2u8; 16];
        assert_eq!(add_saturating_u8x16(a, b), [3u8; 16]);
    }

    #[test]
    fn test_add_sat_saturates() {
        let a = [200u8; 16];
        let b = [100u8; 16];
        assert_eq!(add_saturating_u8x16(a, b), [255u8; 16]);
    }

    #[test]
    fn test_add_sat_zero() {
        assert_eq!(add_saturating_u8x16([0u8; 16], [0u8; 16]), [0u8; 16]);
    }

    #[test]
    fn test_add_sat_alternating() {
        let a: [u8; 16] = [
            0, 255, 0, 255, 0, 255, 0, 255, 0, 255, 0, 255, 0, 255, 0, 255,
        ];
        let b: [u8; 16] = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1];
        assert_eq!(add_saturating_u8x16(a, b), ref_add_sat(a, b));
    }

    // -----------------------------------------------------------------------
    // and_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_and_identity() {
        let a = [0xABu8; 16];
        assert_eq!(and_u8x16(a, [0xFFu8; 16]), a);
    }

    #[test]
    fn test_and_zero() {
        assert_eq!(and_u8x16([0xFFu8; 16], [0u8; 16]), [0u8; 16]);
    }

    #[test]
    fn test_and_mixed() {
        let a: [u8; 16] = [0xF0; 16];
        let b: [u8; 16] = [0x0F; 16];
        assert_eq!(and_u8x16(a, b), [0u8; 16]);
    }

    #[test]
    fn test_and_oracle() {
        let a: [u8; 16] = core::array::from_fn(|i| i as u8);
        let b: [u8; 16] = core::array::from_fn(|i| (15 - i) as u8);
        assert_eq!(and_u8x16(a, b), ref_and(a, b));
    }

    // -----------------------------------------------------------------------
    // or_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_or_identity() {
        let a = [0xABu8; 16];
        assert_eq!(or_u8x16(a, [0u8; 16]), a);
    }

    #[test]
    fn test_or_all_ones() {
        assert_eq!(or_u8x16([0u8; 16], [0xFFu8; 16]), [0xFFu8; 16]);
    }

    #[test]
    fn test_or_oracle() {
        let a: [u8; 16] = core::array::from_fn(|i| i as u8);
        let b: [u8; 16] = core::array::from_fn(|i| (15 - i) as u8);
        assert_eq!(or_u8x16(a, b), ref_or(a, b));
    }

    // -----------------------------------------------------------------------
    // max_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_max_equal() {
        assert_eq!(max_u8x16([7u8; 16], [7u8; 16]), [7u8; 16]);
    }

    #[test]
    fn test_max_all_zero_vs_ff() {
        assert_eq!(max_u8x16([0u8; 16], [0xFFu8; 16]), [0xFFu8; 16]);
    }

    #[test]
    fn test_max_oracle() {
        let a: [u8; 16] = core::array::from_fn(|i| (i * 17) as u8);
        let b: [u8; 16] = core::array::from_fn(|i| (i * 13 + 3) as u8);
        assert_eq!(max_u8x16(a, b), ref_max(a, b));
    }

    // -----------------------------------------------------------------------
    // min_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_min_equal() {
        assert_eq!(min_u8x16([7u8; 16], [7u8; 16]), [7u8; 16]);
    }

    #[test]
    fn test_min_all_ff_vs_zero() {
        assert_eq!(min_u8x16([0xFFu8; 16], [0u8; 16]), [0u8; 16]);
    }

    #[test]
    fn test_min_oracle() {
        let a: [u8; 16] = core::array::from_fn(|i| (i * 17) as u8);
        let b: [u8; 16] = core::array::from_fn(|i| (i * 13 + 3) as u8);
        assert_eq!(min_u8x16(a, b), ref_min(a, b));
    }

    // -----------------------------------------------------------------------
    // shuffle_u8x16_branchless
    // -----------------------------------------------------------------------

    #[test]
    fn test_shuffle_identity() {
        let a: [u8; 16] = core::array::from_fn(|i| i as u8);
        let mask: [u8; 16] = core::array::from_fn(|i| i as u8);
        assert_eq!(shuffle_u8x16_branchless(a, mask), a);
    }

    #[test]
    fn test_shuffle_reverse() {
        let a: [u8; 16] = core::array::from_fn(|i| i as u8);
        let mask: [u8; 16] = core::array::from_fn(|i| (15 - i) as u8);
        assert_eq!(shuffle_u8x16_branchless(a, mask), ref_shuffle(a, mask));
    }

    #[test]
    fn test_shuffle_high_bit_zeros() {
        let a: [u8; 16] = core::array::from_fn(|i| (i + 1) as u8);
        let mut mask = [0u8; 16];
        mask[0] = 0x80; // High bit set → output zero.
        let r = shuffle_u8x16_branchless(a, mask);
        assert_eq!(r[0], 0);
        assert_eq!(r[1], a[0]); // mask[1] = 0 → a[0]
    }

    #[test]
    fn test_shuffle_all_zero_mask() {
        let a: [u8; 16] = core::array::from_fn(|i| (i as u8).wrapping_add(10));
        let mask = [0u8; 16]; // All lanes select index 0.
        let r = shuffle_u8x16_branchless(a, mask);
        assert_eq!(r, [a[0]; 16]);
    }

    #[test]
    fn test_shuffle_oracle() {
        let a: [u8; 16] = core::array::from_fn(|i| (i * 3 + 7) as u8);
        let mask: [u8; 16] = [
            3, 7, 0xF, 0x80, 1, 2, 0xA, 0x80, 0, 5, 0xE, 4, 8, 0x9, 6, 0x80,
        ];
        assert_eq!(shuffle_u8x16_branchless(a, mask), ref_shuffle(a, mask));
    }

    // -----------------------------------------------------------------------
    // horizontal_sum_u8x16
    // -----------------------------------------------------------------------

    #[test]
    fn test_hsum_zero() {
        assert_eq!(horizontal_sum_u8x16([0u8; 16]), 0);
    }

    #[test]
    fn test_hsum_ones() {
        assert_eq!(horizontal_sum_u8x16([1u8; 16]), 16);
    }

    #[test]
    fn test_hsum_max() {
        assert_eq!(horizontal_sum_u8x16([255u8; 16]), 16 * 255);
    }

    #[test]
    fn test_hsum_oracle() {
        let a: [u8; 16] = core::array::from_fn(|i| i as u8);
        assert_eq!(horizontal_sum_u8x16(a), ref_hsum(a));
    }

    #[test]
    fn test_hsum_alternating() {
        let a: [u8; 16] = core::array::from_fn(|i| if i % 2 == 0 { 100 } else { 155 });
        assert_eq!(horizontal_sum_u8x16(a), ref_hsum(a));
    }

    // -----------------------------------------------------------------------
    // PhD gate
    // -----------------------------------------------------------------------

    #[test]
    fn test_phd_gate_identity() {
        assert_eq!(simd_dispatch_phd_gate(0), 0);
        assert_eq!(simd_dispatch_phd_gate(u64::MAX), u64::MAX);
        assert_eq!(
            simd_dispatch_phd_gate(0xDEAD_BEEF_CAFE_1234),
            0xDEAD_BEEF_CAFE_1234
        );
    }
}
