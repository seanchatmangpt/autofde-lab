// SAFETY_LEVEL: no unsafe code permitted in algorithm modules
#[no_mangle]
pub fn quotient_filter_add_u64(val: u64, aux: u64) -> u64 {
    let nonzero = (((val | 0x8080_8080_8080_8080).wrapping_sub(0x0101_0101_0101_0101)) | val)
        & 0x8080_8080_8080_8080;
    let zero_bytes = !nonzero & 0x8080_8080_8080_8080;
    let tz = zero_bytes.trailing_zeros();
    let shift = tz & 0x38; // nearest byte boundary
    let mask = (0xFFu64).wrapping_shl(shift);
    let has_zero = (zero_bytes != 0) as u64;
    let insert = ((aux & 0xFF).wrapping_shl(shift)) & mask;
    val | (insert * has_zero)
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_quotient(val: u64, aux: u64) -> u64 {
        let mut v = val.to_le_bytes();
        let fp = (aux & 0xFF) as u8;
        for i in 0..8 {
            if v[i] == 0 {
                v[i] = fp;
                break;
            }
        }
        u64::from_le_bytes(v)
    }

    proptest! {
        #[test]
        fn test_quotient_fuzz(val in any::<u64>(), aux in any::<u64>()) {
            prop_assert_eq!(quotient_filter_add_u64(val, aux), reference_quotient(val, aux));
        }
    }
}
