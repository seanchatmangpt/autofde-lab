// SAFETY_LEVEL: no unsafe code permitted in algorithm modules
#[no_mangle]
pub fn hazard_pointer_retire(val: u64, aux: u64) -> u64 {
    // Mask pointer (val) with an epoch tag (aux) to safely retire.
    let ptr_mask = 0x0000_FFFF_FFFF_F000u64;
    let epoch_mask = 0xFFFF_0000_0000_0FFFu64;
    (val & ptr_mask) | (aux & epoch_mask)
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // Independent oracle: bit-by-bit selection. The pointer field is bits
    // 12..=47 (taken from `val`); all other bits (the epoch tag) are taken
    // from `aux`. This is a structurally different formulation than the
    // SWAR mask-and-or used by the implementation.
    fn reference_hazard(val: u64, aux: u64) -> u64 {
        let mut out = 0u64;
        for bit in 0..64 {
            let from_ptr = (12..=47).contains(&bit);
            let src = if from_ptr { val } else { aux };
            out |= ((src >> bit) & 1) << bit;
        }
        out
    }

    proptest! {
        #[test]
        fn test_hazard_fuzz(val in any::<u64>(), aux in any::<u64>()) {
            prop_assert_eq!(hazard_pointer_retire(val, aux), reference_hazard(val, aux));
        }
    }

    // Known-answer vectors derived by hand from the field layout.
    #[test]
    fn test_hazard_known_answers() {
        // All bits from val are kept only in the pointer field (bits 12..47).
        assert_eq!(hazard_pointer_retire(u64::MAX, 0), 0x0000_FFFF_FFFF_F000);
        // All bits from aux are kept only in the epoch field (the complement).
        assert_eq!(hazard_pointer_retire(0, u64::MAX), 0xFFFF_0000_0000_0FFF);
        // The two fields are complementary and cover all 64 bits.
        assert_eq!(hazard_pointer_retire(u64::MAX, u64::MAX), u64::MAX);
    }
}
