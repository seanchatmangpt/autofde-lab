// SAFETY_LEVEL: no unsafe code permitted in algorithm modules
#[no_mangle]
pub fn jaro_winkler_branchless(val: u64, aux: u64) -> u64 {
    let v = val.to_le_bytes();
    let a = aux.to_le_bytes();
    let mut matches = 0u64;

    let mut i: usize = 0;
    while i < 8 {
        let mut matched = 0u64;
        let mut j: usize = 0;
        while j < 8 {
            let dist = i.abs_diff(j);
            let in_window = (dist <= 3) as u64;
            let eq = (v[i] == a[j]) as u64;
            matched |= in_window & eq;
            j += 1;
        }
        matches += matched;
        i += 1;
    }
    matches
}

#[cfg(test)]
mod tests {
    use super::*;

    // Known-answer vectors derived BY HAND from the definition:
    // count of byte positions i in 0..8 such that some j in 0..8 has
    // |i - j| <= 3 and v[i] == a[j].  Bytes are little-endian.
    #[test]
    fn test_jaro_known_answers() {
        // All-zero vs all-zero: every i matches j=i (dist 0) -> 8.
        assert_eq!(
            jaro_winkler_branchless(0x0000_0000_0000_0000, 0x0000_0000_0000_0000),
            8
        );
        // All-ones bytes vs all-ones bytes -> 8.
        assert_eq!(
            jaro_winkler_branchless(0x0101_0101_0101_0101, 0x0101_0101_0101_0101),
            8
        );
        // v bytes [0,1,2,3,4,5,6,7] vs a all 0xFF: no byte of v appears in a -> 0.
        assert_eq!(
            jaro_winkler_branchless(0x0706_0504_0302_0100, 0xFFFF_FFFF_FFFF_FFFF),
            0
        );
        // v=[9,0,0,0,0,0,0,0], a=[0,0,0,0,9,0,0,0]:
        //   i=0 (v=9): a's only 9 is at j=4, |0-4|=4 > 3 -> no match.
        //   i=1..7 (v=0): each finds a 0 within distance 3 -> matched.
        //   total = 7.
        assert_eq!(
            jaro_winkler_branchless(0x0000_0000_0000_0009, 0x0000_0009_0000_0000),
            7
        );
    }
}
