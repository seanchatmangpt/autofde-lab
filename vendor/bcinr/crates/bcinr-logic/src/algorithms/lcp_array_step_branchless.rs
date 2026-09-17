// SAFETY_LEVEL: no unsafe code permitted in algorithm modules
#[no_mangle]
pub fn lcp_array_step_branchless(val: u64, aux: u64) -> u64 {
    let diff = val ^ aux;
    const LO: u64 = 0x0101_0101_0101_0101;
    const HI: u64 = 0x8080_8080_8080_8080;
    let nonzero = (((diff | HI).wrapping_sub(LO)) | diff) & HI;
    (nonzero.trailing_zeros() as u64) >> 3
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn reference_lcp(val: u64, aux: u64) -> u64 {
        let v = val.to_le_bytes();
        let a = aux.to_le_bytes();
        let mut count = 0;
        for i in 0..8 {
            if v[i] == a[i] {
                count += 1;
            } else {
                break;
            }
        }
        count
    }

    proptest! {
        #[test]
        fn test_lcp_fuzz(val in any::<u64>(), aux in any::<u64>()) {
            prop_assert_eq!(lcp_array_step_branchless(val, aux), reference_lcp(val, aux));
        }
    }
}
