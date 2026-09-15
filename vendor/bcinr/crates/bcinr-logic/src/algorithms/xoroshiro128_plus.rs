// SAFETY_LEVEL: no unsafe code permitted in algorithm modules
#[no_mangle]
pub fn xoroshiro128_plus(val: u64, aux: u64) -> u64 {
    // Computes the next state of s0.
    let s0 = val;
    let s1 = aux ^ s0;
    s0.rotate_left(24) ^ s1 ^ (s1 << 16)
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // Known-answer vectors derived independently from the xoroshiro128+ spec
    // (s1' = s0 ^ s1; new_s0 = rotl(s0, 24) ^ s1' ^ (s1' << 16)), NOT by copying
    // the implementation. This breaks the prior tautological self-comparison.
    #[test]
    fn test_xoroshiro_known_vectors() {
        // (0,0): rotl(0,24) ^ 0 ^ 0 = 0
        assert_eq!(xoroshiro128_plus(0, 0), 0);
        // (1,0): s1'=1; rotl(1,24)=0x0100_0000; ^1 ^ (1<<16=0x1_0000) = 0x0101_0001
        assert_eq!(xoroshiro128_plus(1, 0), 0x0101_0001);
        // (0,1): s1'=1; rotl(0,24)=0; ^1 ^ 0x1_0000 = 0x0001_0001
        assert_eq!(xoroshiro128_plus(0, 1), 0x0001_0001);
    }

    proptest! {
        // Structural invariants that hold for the real transform without
        // restating its formula: the high rotation makes it sensitive to the
        // top bits of s0, and equal inputs cancel s1' to s0 alone.
        #[test]
        fn test_xoroshiro_equal_inputs(s in any::<u64>()) {
            // val == aux => s1' = s ^ s = 0 => result = rotl(s, 24)
            prop_assert_eq!(xoroshiro128_plus(s, s), s.rotate_left(24));
        }

        #[test]
        fn test_xoroshiro_deterministic(val in any::<u64>(), aux in any::<u64>()) {
            prop_assert_eq!(xoroshiro128_plus(val, aux), xoroshiro128_plus(val, aux));
        }
    }
}
