use crate::allocator::StabilityRefusal;

#[derive(Copy, Clone, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct CanonicalMask {
    pub val: u32,
}

impl CanonicalMask {
    pub const TRUE: Self = Self { val: u32::MAX };
    pub const FALSE: Self = Self { val: 0 };

    #[inline(always)]
    pub const fn select_u32(self, a: u32, b: u32) -> u32 {
        (a & self.val) | (b & !self.val)
    }

    #[inline(always)]
    pub const fn select_i32(self, a: i32, b: i32) -> i32 {
        (a & self.val as i32) | (b & !(self.val as i32))
    }
}

/// Branchless Contract: Constant-time less-than comparison for u32.
#[inline(always)]
pub const fn const_lt_u32(a: u32, b: u32) -> CanonicalMask {
    let diff = ((a ^ ((a ^ b) | (a.wrapping_sub(b) ^ b))) >> 31) & 1;
    CanonicalMask {
        val: 0u32.wrapping_sub(diff),
    }
}

/// Branchless Contract: Constant-time equality comparison for u32.
#[inline(always)]
pub const fn const_eq_u32(a: u32, b: u32) -> CanonicalMask {
    let x = a ^ b;
    #[cfg(not(feature = "mutant_7"))]
    let nonzero = (x | x.wrapping_neg()) >> 31;
    #[cfg(feature = "mutant_7")]
    let nonzero = (!x & !x.wrapping_neg()) >> 31; // Mutated: sign inversion
    CanonicalMask {
        val: 0u32.wrapping_sub(1u32.wrapping_sub(nonzero)),
    }
}

#[inline(always)]
pub const fn const_lt_i32(a: i32, b: i32) -> CanonicalMask {
    let diff = (a as u32).wrapping_sub(b as u32);
    let a_sign = (a as u32) >> 31;
    let b_sign = (b as u32) >> 31;
    let diff_sign = diff >> 31;
    let res = (a_sign & (b_sign ^ 1)) | ((!(a_sign ^ b_sign)) & diff_sign);
    CanonicalMask {
        val: 0u32.wrapping_sub(res),
    }
}

#[inline(always)]
pub const fn const_eq_i32(a: i32, b: i32) -> CanonicalMask {
    const_eq_u32(a as u32, b as u32)
}

#[inline(always)]
pub const fn branchless_err_acc(e1: u32, e2: u32) -> u32 {
    let e1_is_ok = const_eq_u32(e1, u32::MAX);
    e1_is_ok.select_u32(e2, e1)
}

#[derive(Copy, Clone, Default, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub struct NonNegativeFixed {
    pub val: u32,
    pub err: u32,
}

impl NonNegativeFixed {
    pub const ZERO: Self = Self {
        val: 0,
        err: u32::MAX,
    };
    pub const ONE: Self = Self {
        val: 65536,
        err: u32::MAX,
    };
    pub const MAX: Self = Self {
        val: u32::MAX,
        err: u32::MAX,
    };

    #[inline(always)]
    pub const fn from_bits(bits: u32) -> Self {
        Self {
            val: bits,
            err: u32::MAX,
        }
    }
    #[inline(always)]
    pub const fn to_bits(self) -> u32 {
        self.val
    }
    #[inline(always)]
    pub const fn from_num(num: u32) -> Self {
        Self {
            val: num.wrapping_shl(16),
            err: u32::MAX,
        }
    }
    #[inline(always)]
    pub const fn to_num(self) -> u32 {
        self.val >> 16
    }

    #[inline(always)]
    pub const fn saturating_add(self, other: Self) -> Self {
        let sum = self.val.wrapping_add(other.val);
        #[cfg(not(feature = "mutant_6"))]
        let overflow = const_lt_u32(sum, self.val);
        #[cfg(feature = "mutant_6")]
        let overflow = const_lt_u32(self.val, sum); // Mutated: inverted overflow condition
        let e = overflow.select_u32(StabilityRefusal::NumericRangeExceeded as u32, u32::MAX);
        Self {
            val: overflow.select_u32(u32::MAX, sum),
            err: branchless_err_acc(self.err, branchless_err_acc(other.err, e)),
        }
    }

    #[inline(always)]
    pub const fn saturating_sub(self, other: Self) -> Self {
        let underflow = const_lt_u32(self.val, other.val);
        let e = underflow.select_u32(StabilityRefusal::NumericRangeExceeded as u32, u32::MAX);
        Self {
            val: underflow.select_u32(0, self.val.wrapping_sub(other.val)),
            err: branchless_err_acc(self.err, branchless_err_acc(other.err, e)),
        }
    }

    #[inline(always)]
    pub const fn saturating_mul(self, other: Self) -> Self {
        let prod = (self.val as u64).wrapping_mul(other.val as u64);
        let res_u64 = prod >> 16;
        let high = (res_u64 >> 32) as u32;
        let overflow = (high | high.wrapping_neg()) >> 31;
        let overflow_mask = CanonicalMask {
            val: 0u32.wrapping_sub(overflow),
        };
        let e = overflow_mask.select_u32(StabilityRefusal::NumericRangeExceeded as u32, u32::MAX);
        Self {
            val: overflow_mask.select_u32(u32::MAX, res_u64 as u32),
            err: branchless_err_acc(self.err, branchless_err_acc(other.err, e)),
        }
    }

    #[inline(always)]
    pub const fn saturating_div(self, other: Self) -> Self {
        let den_is_zero = const_eq_u32(other.val, 0);
        let d = den_is_zero.select_u32(1, other.val);

        let lz = d.leading_zeros();
        // `wrapping_shl`, not `<<`: the zero-divisor guard above makes
        // `d >= 1` (hence `lz <= 31`) for every lawful input, so the two are
        // bit-identical in production. But if that guard is ever corrupted
        // (e.g. an inverted `const_eq_u32` mask under a hostile mutant), a
        // `d == 0` divisor gives `lz == 32` and `d << lz` panics in debug
        // builds -- turning the mutant's kill evidence into a panic path
        // instead of the typed refusal the suite asserts. Masking the shift
        // amount (as `log2` below already does for its normalization) keeps
        // the corrupted path executing so the err-tag/refusal machinery can
        // report it.
        let d_norm = d.wrapping_shl(lz);

        let a_scale = 13021703673752174592u64;
        let b_coeff = 2021160080u64;
        let x0 = a_scale.wrapping_sub(b_coeff.wrapping_mul(d_norm as u64));

        let e0 = (1i128 << 94) - (d_norm as i128) * (x0 as i128);
        let x1 = ((x0 as i128) + (((x0 as i128) * (e0 >> 32)) >> 62)) as u64;

        let e1 = (1i128 << 94) - (d_norm as i128) * (x1 as i128);
        let x2 = ((x1 as i128) + (((x1 as i128) * (e1 >> 32)) >> 62)) as u64;

        let e2 = (1i128 << 94) - (d_norm as i128) * (x2 as i128);
        let x3 = ((x2 as i128) + (((x2 as i128) * (e2 >> 32)) >> 62)) as u64;

        let n = self.val as u128;
        let q_u128 = n.wrapping_mul(x3 as u128);
        let q_shifted_46 = (q_u128 >> 46) as u64;
        let q = q_shifted_46 >> (32 - lz);

        let rem = ((self.val as u64) << 16).wrapping_sub(q.wrapping_mul(d as u64)) as i64;

        let is_lt = ((rem >> 63) & 1) as u64;
        let diff = rem.wrapping_sub(d as i64);
        let is_ge = (((!diff) >> 63) & 1) as u64;

        let q_corrected = q.wrapping_add(is_ge).wrapping_sub(is_lt);

        let overflow_1 = const_lt_u32(u32::MAX, (q_corrected >> 32) as u32).val;
        let overflow_2 = 0u32.wrapping_sub((q_corrected > u32::MAX as u64) as u32);
        let overflow = CanonicalMask {
            val: overflow_1 | overflow_2,
        };

        let saturate = CanonicalMask {
            val: overflow.val | den_is_zero.val,
        };

        let e = den_is_zero.select_u32(
            StabilityRefusal::UnsupportedDomain as u32,
            overflow.select_u32(StabilityRefusal::NumericRangeExceeded as u32, u32::MAX),
        );
        Self {
            val: saturate.select_u32(u32::MAX, q_corrected as u32),
            err: branchless_err_acc(self.err, branchless_err_acc(other.err, e)),
        }
    }

    #[inline(always)]
    pub fn log2(self) -> SignedFixed {
        let x = self.val as u64;
        let lz = x.leading_zeros();
        let nz = ((x | x.wrapping_neg()) >> 63) & 1;
        let ip = 63u64.wrapping_sub(lz as u64) & nz.wrapping_neg();

        let mantissa = x.wrapping_shl(lz.wrapping_add(1));
        let f = (mantissa >> (64 - 16)) as u32;

        let diff = 65536 - f;
        let correction = (f * diff) >> 16;
        let corrected_frac = f + ((correction * 29013) >> 16);

        let res = (ip << 16).wrapping_add(corrected_frac as u64);

        #[cfg(not(feature = "mutant_8"))]
        let is_zero = const_eq_u32(self.val, 0);
        #[cfg(feature = "mutant_8")]
        let is_zero = const_eq_u32(0, 0); // Mutated: always true
        let computed = (res as u32).wrapping_sub(16 << 16) as i32;
        let e = is_zero.select_u32(StabilityRefusal::UnsupportedDomain as u32, u32::MAX);
        SignedFixed {
            val: is_zero.select_i32(-1048576, computed),
            err: branchless_err_acc(self.err, e),
        }
    }
}

#[derive(Copy, Clone, Default, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub struct SignedFixed {
    pub val: i32,
    pub err: u32,
}

impl SignedFixed {
    pub const ZERO: Self = Self {
        val: 0,
        err: u32::MAX,
    };
    pub const ONE: Self = Self {
        val: 65536,
        err: u32::MAX,
    };
    pub const MAX: Self = Self {
        val: i32::MAX,
        err: u32::MAX,
    };
    pub const MIN: Self = Self {
        val: i32::MIN,
        err: u32::MAX,
    };

    #[inline(always)]
    pub const fn from_bits(bits: i32) -> Self {
        Self {
            val: bits,
            err: u32::MAX,
        }
    }
    #[inline(always)]
    pub const fn to_bits(self) -> i32 {
        self.val
    }
    #[inline(always)]
    pub const fn from_num(num: i32) -> Self {
        Self {
            val: num.wrapping_shl(16),
            err: u32::MAX,
        }
    }
    #[inline(always)]
    pub const fn to_num(self) -> i32 {
        self.val >> 16
    }

    #[inline(always)]
    pub const fn saturating_add(self, other: Self) -> Self {
        let (sum, overflow) = self.val.overflowing_add(other.val);
        let is_neg = const_lt_i32(self.val, 0);
        let sat_val = is_neg.select_i32(i32::MIN, i32::MAX);
        let overflow_mask = CanonicalMask {
            val: 0u32.wrapping_sub(overflow as u32),
        };
        let e = overflow_mask.select_u32(StabilityRefusal::NumericRangeExceeded as u32, u32::MAX);
        Self {
            val: overflow_mask.select_i32(sat_val, sum),
            err: branchless_err_acc(self.err, branchless_err_acc(other.err, e)),
        }
    }

    #[inline(always)]
    pub const fn saturating_sub(self, other: Self) -> Self {
        let (diff, overflow) = self.val.overflowing_sub(other.val);
        let is_neg = const_lt_i32(self.val, 0);
        let sat_val = is_neg.select_i32(i32::MIN, i32::MAX);
        let overflow_mask = CanonicalMask {
            val: 0u32.wrapping_sub(overflow as u32),
        };
        let e = overflow_mask.select_u32(StabilityRefusal::NumericRangeExceeded as u32, u32::MAX);
        Self {
            val: overflow_mask.select_i32(sat_val, diff),
            err: branchless_err_acc(self.err, branchless_err_acc(other.err, e)),
        }
    }

    #[inline(always)]
    pub const fn saturating_mul(self, other: Self) -> Self {
        let prod = (self.val as i64).wrapping_mul(other.val as i64);
        let res_i64 = prod >> 16;

        let overflow_max = CanonicalMask {
            val: 0u32.wrapping_sub((res_i64 > i32::MAX as i64) as u32),
        };
        let overflow_min = CanonicalMask {
            val: 0u32.wrapping_sub((res_i64 < i32::MIN as i64) as u32),
        };

        let mut res = overflow_min.select_i32(i32::MIN, res_i64 as i32);
        res = overflow_max.select_i32(i32::MAX, res);

        let is_overflow = overflow_max.val | overflow_min.val;
        let e = const_eq_u32(is_overflow, 0)
            .select_u32(u32::MAX, StabilityRefusal::NumericRangeExceeded as u32);
        Self {
            val: res,
            err: branchless_err_acc(self.err, branchless_err_acc(other.err, e)),
        }
    }

    #[inline(always)]
    pub fn exp2(self) -> NonNegativeFixed {
        let x = self.val;
        let ip = x >> 16;
        let fp = x.wrapping_sub(ip.wrapping_shl(16));

        let y = fp as u32;
        let res1 = (y.wrapping_mul(630)) >> 16;
        let res2 = (y.wrapping_mul(3637u32.wrapping_add(res1))) >> 16;
        let res3 = (y.wrapping_mul(15763u32.wrapping_add(res2))) >> 16;
        let res4 = (y.wrapping_mul(45506u32.wrapping_add(res3))) >> 16;
        let frac_part = 65536u32.wrapping_add(res4);

        let is_overflow = CanonicalMask {
            val: 0u32.wrapping_sub(((((ip.wrapping_sub(16)) >> 31) ^ 1) & 1) as u32),
        };
        let is_underflow = CanonicalMask {
            val: 0u32.wrapping_sub((((((-17i32).wrapping_sub(ip)) >> 31) ^ 1) & 1) as u32),
        };

        let shl = (ip & 31) as u32;
        let shr = ((ip.wrapping_neg()) & 31) as u32;

        let val_shl = frac_part.wrapping_shl(shl);
        let val_shr = frac_part.wrapping_shr(shr);

        let ip_neg = CanonicalMask {
            val: 0u32.wrapping_sub(((ip >> 31) & 1) as u32),
        };
        let val_shifted = ip_neg.select_u32(val_shr, val_shl);

        let res = is_overflow.select_u32(u32::MAX, is_underflow.select_u32(0, val_shifted));
        let e = const_eq_u32(is_overflow.val | is_underflow.val, 0)
            .select_u32(u32::MAX, StabilityRefusal::NumericRangeExceeded as u32);
        NonNegativeFixed {
            val: res,
            err: branchless_err_acc(self.err, e),
        }
    }

    #[inline(always)]
    pub fn exp(self) -> NonNegativeFixed {
        let x = self.val;
        let z = (((x as i64).wrapping_mul(94548)) >> 16) as i32;
        SignedFixed {
            val: z,
            err: self.err,
        }
        .exp2()
    }
}

impl core::ops::Add for NonNegativeFixed {
    type Output = Self;
    #[inline(always)]
    fn add(self, other: Self) -> Self {
        self.saturating_add(other)
    }
}
impl core::ops::Sub for NonNegativeFixed {
    type Output = Self;
    #[inline(always)]
    fn sub(self, other: Self) -> Self {
        self.saturating_sub(other)
    }
}
impl core::ops::Mul for NonNegativeFixed {
    type Output = Self;
    #[inline(always)]
    fn mul(self, other: Self) -> Self {
        self.saturating_mul(other)
    }
}
impl core::ops::Div for NonNegativeFixed {
    type Output = Self;
    #[inline(always)]
    fn div(self, other: Self) -> Self {
        self.saturating_div(other)
    }
}
impl core::ops::AddAssign for NonNegativeFixed {
    #[inline(always)]
    fn add_assign(&mut self, other: Self) {
        *self = *self + other;
    }
}
impl core::ops::SubAssign for NonNegativeFixed {
    #[inline(always)]
    fn sub_assign(&mut self, other: Self) {
        *self = *self - other;
    }
}
impl core::ops::MulAssign for NonNegativeFixed {
    #[inline(always)]
    fn mul_assign(&mut self, other: Self) {
        *self = *self * other;
    }
}
impl core::ops::DivAssign for NonNegativeFixed {
    #[inline(always)]
    fn div_assign(&mut self, other: Self) {
        *self = *self / other;
    }
}

impl core::ops::Add for SignedFixed {
    type Output = Self;
    #[inline(always)]
    fn add(self, other: Self) -> Self {
        self.saturating_add(other)
    }
}
impl core::ops::Sub for SignedFixed {
    type Output = Self;
    #[inline(always)]
    fn sub(self, other: Self) -> Self {
        self.saturating_sub(other)
    }
}
impl core::ops::Mul for SignedFixed {
    type Output = Self;
    #[inline(always)]
    fn mul(self, other: Self) -> Self {
        self.saturating_mul(other)
    }
}
impl core::ops::AddAssign for SignedFixed {
    #[inline(always)]
    fn add_assign(&mut self, other: Self) {
        *self = *self + other;
    }
}
impl core::ops::SubAssign for SignedFixed {
    #[inline(always)]
    fn sub_assign(&mut self, other: Self) {
        *self = *self - other;
    }
}
impl core::ops::MulAssign for SignedFixed {
    #[inline(always)]
    fn mul_assign(&mut self, other: Self) {
        *self = *self * other;
    }
}
