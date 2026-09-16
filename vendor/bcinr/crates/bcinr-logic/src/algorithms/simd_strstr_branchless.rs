// SAFETY_LEVEL: no unsafe code permitted in algorithm modules
#[no_mangle]
pub fn simd_strstr_branchless(val: u64, aux: u64) -> u64 {
    let needle = (aux & 0xFF).wrapping_mul(0x0101_0101_0101_0101);
    let diff = val ^ needle;
    const LO: u64 = 0x0101_0101_0101_0101;
    const HI: u64 = 0x8080_8080_8080_8080;
    let nonzero = (((diff | HI).wrapping_sub(LO)) | diff) & HI;
    let zero_bytes = !nonzero & HI;
    let found = (zero_bytes != 0) as u64;
    (zero_bytes.trailing_zeros() as u64 >> 3) * found + 8 * (1 - found)
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_strstr(val: u64, aux: u64) -> u64 {
        let v = val.to_le_bytes();
        let needle = (aux & 0xFF) as u8;
        let mut res = 8;
        for i in 0..8 {
            if v[i] == needle {
                res = i as u64;
                break;
            }
        }
        res
    }

    proptest! {
        #[test]
        fn test_strstr_fuzz(val in any::<u64>(), aux in any::<u64>()) {
            prop_assert_eq!(simd_strstr_branchless(val, aux), reference_strstr(val, aux));
        }
    }
}
