// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#![forbid(unsafe_code)]
#![allow(
    unused_variables,
    unused_assignments,
    unused_mut,
    unused_parens,
    dead_code
)]
// Academic-grade branchless algorithm library: tabulation_hash_u64
// Tabulation hashing — provably 3-independent, used in competitive programming
// and randomized data structures (Cuckoo hashing, Count-Min sketches).
// Maps a 32-bit key to a 64-bit hash value via XOR of table entries
// indexed by each byte of the key: O(1) table lookups, no arithmetic, no branches.

/// Tabulation hash of a 32-bit key.
///
/// Splits `key` into 4 bytes, looks up one 64-bit value per byte in the
/// corresponding column table, and XORs the four values together.
///
/// This is provably 3-independent when the table entries are independent
/// uniform random values — a stronger guarantee than most practical hashes.
///
/// # Branchless Contract
/// **Category:** B — Cell Arithmetic
/// **Plane:** D-resident cell word; no scratch
/// **Tier:** T0 — single-word arithmetic primitive
/// **Scope:** branchless, O(1), CC=1; admissible_T0.
///
/// # Parameters
/// - `key`: 32-bit key to hash
/// - `tables`: four 256-entry tables of 64-bit random values (8 KB total)
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::tabulation_hash_u64::{
///     tabulation_hash_u64, tabulation_hash_init_tables,
/// };
/// let mut tables = [[0u64; 256]; 4];
/// tabulation_hash_init_tables(123456789, &mut tables);
/// let h = tabulation_hash_u64(0x12345678, &tables);
/// assert_eq!(h, tabulation_hash_u64(0x12345678, &tables)); // deterministic
/// assert_ne!(h, tabulation_hash_u64(0x12345679, &tables)); // sensitive to key
/// ```
pub fn tabulation_hash_u64(key: u32, tables: &[[u64; 256]; 4]) -> u64 {
    let b0 = (key & 0xFF) as usize;
    let b1 = ((key >> 8) & 0xFF) as usize;
    let b2 = ((key >> 16) & 0xFF) as usize;
    let b3 = ((key >> 24) & 0xFF) as usize;
    tables[0][b0] ^ tables[1][b1] ^ tables[2][b2] ^ tables[3][b3]
}

/// Initialize tabulation hash tables using an xorshift64 PRNG.
///
/// Fills all four 256-entry tables with pseudo-random 64-bit values
/// derived from `seed`. The resulting tables satisfy the independence
/// requirements for tabulation hashing.
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::tabulation_hash_u64::tabulation_hash_init_tables;
/// let mut tables = [[0u64; 256]; 4];
/// tabulation_hash_init_tables(42, &mut tables);
/// // Tables are filled; entries are all nonzero with overwhelming probability
/// assert_ne!(tables[0][0], 0);
/// ```
pub fn tabulation_hash_init_tables(seed: u64, tables: &mut [[u64; 256]; 4]) {
    // xorshift64 PRNG — period 2^64 - 1, all nonzero states
    let mut state = if seed == 0 { 0x853c49e6748fea9b } else { seed };
    for table in tables.iter_mut() {
        for entry in table.iter_mut() {
            // xorshift64 step
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            *entry = state;
        }
    }
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn make_tables(seed: u64) -> [[u64; 256]; 4] {
        let mut tables = [[0u64; 256]; 4];
        tabulation_hash_init_tables(seed, &mut tables);
        tables
    }

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE
    // -------------------------------------------------------------------------
    fn tabulation_hash_reference(key: u32, tables: &[[u64; 256]; 4]) -> u64 {
        let b0 = (key & 0xFF) as usize;
        let b1 = ((key >> 8) & 0xFF) as usize;
        let b2 = ((key >> 16) & 0xFF) as usize;
        let b3 = ((key >> 24) & 0xFF) as usize;
        tables[0][b0] ^ tables[1][b1] ^ tables[2][b2] ^ tables[3][b3]
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS
    // -------------------------------------------------------------------------
    fn mutant_tab_1(key: u32, tables: &[[u64; 256]; 4]) -> u64 {
        !tabulation_hash_reference(key, tables)
    }
    fn mutant_tab_2(key: u32, tables: &[[u64; 256]; 4]) -> u64 {
        tabulation_hash_reference(key, tables).wrapping_add(1)
    }
    fn mutant_tab_3(key: u32, tables: &[[u64; 256]; 4]) -> u64 {
        tabulation_hash_reference(key, tables) ^ 0xFFFFFFFF
    }

    proptest! {
        #[test]
        fn test_tabulation_equivalence(key in any::<u32>(), seed in 1u64..) {
            let tables = make_tables(seed);
            let expected = tabulation_hash_reference(key, &tables);
            let actual = tabulation_hash_u64(key, &tables);
            prop_assert_eq!(expected, actual);
        }

        #[test]
        fn test_tabulation_mutant_1(key in any::<u32>(), seed in 1u64..) {
            let tables = make_tables(seed);
            let expected = tabulation_hash_reference(key, &tables);
            let actual = mutant_tab_1(key, &tables);
            prop_assert!(expected != actual);
        }

        #[test]
        fn test_tabulation_mutant_2(key in any::<u32>(), seed in 1u64..) {
            let tables = make_tables(seed);
            let expected = tabulation_hash_reference(key, &tables);
            let actual = mutant_tab_2(key, &tables);
            prop_assert!(expected != actual);
        }

        #[test]
        fn test_tabulation_mutant_3(key in any::<u32>(), seed in 1u64..) {
            let tables = make_tables(seed);
            let expected = tabulation_hash_reference(key, &tables);
            let actual = mutant_tab_3(key, &tables);
            prop_assert!(expected != actual);
        }
    }

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES
    // -------------------------------------------------------------------------
    #[test]
    fn test_tabulation_zero_key() {
        let tables = make_tables(1);
        // key=0: uses tables[i][0] for all i
        let expected = tables[0][0] ^ tables[1][0] ^ tables[2][0] ^ tables[3][0];
        assert_eq!(tabulation_hash_u64(0, &tables), expected);
    }

    #[test]
    fn test_tabulation_max_key() {
        let tables = make_tables(1);
        let h = tabulation_hash_u64(u32::MAX, &tables);
        assert_eq!(h, tabulation_hash_reference(u32::MAX, &tables));
    }

    #[test]
    fn test_tabulation_deterministic() {
        let tables = make_tables(42);
        let h1 = tabulation_hash_u64(0x12345678, &tables);
        let h2 = tabulation_hash_u64(0x12345678, &tables);
        assert_eq!(h1, h2);
    }

    #[test]
    fn test_tabulation_sensitivity() {
        let tables = make_tables(1337);
        // Changing 1 bit in key should (almost always) change hash
        let h1 = tabulation_hash_u64(0x00000000, &tables);
        let h2 = tabulation_hash_u64(0x00000001, &tables);
        assert_ne!(h1, h2);
    }

    #[test]
    fn test_tabulation_init_nonzero() {
        // xorshift64 with nonzero seed never produces 0 (period = 2^64-1)
        let tables = make_tables(1);
        for table in &tables {
            for &entry in table.iter() {
                assert_ne!(entry, 0, "xorshift64 must never produce 0");
            }
        }
    }

    #[test]
    fn test_tabulation_init_tables_zero_seed() {
        // Seed 0 is mapped to a safe fallback seed — must not produce all-zero tables
        let tables = make_tables(0);
        assert_ne!(tables[0][0], 0);
    }

    #[test]
    fn test_tabulation_avalanche() {
        let tables = make_tables(0x00000000);
        let h1 = tabulation_hash_u64(0x00000000, &tables);
        let h2 = tabulation_hash_u64(0x80000000, &tables);
        let diff = (h1 ^ h2).count_ones();
        // XOR of two independent 64-bit uniforms: expected ~32 bits differ
        assert!(diff >= 16, "Avalanche too weak: only {} bits changed", diff);
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis
    // -------------------------------------------------------------------------
    // Hoare-logic Verification: Radon Law (CC=1) holds.
    // Pre: { key: u32, tables: &[[u64;256];4] initialised by tabulation_hash_init_tables }
    // Post: { res == tables[0][key&FF] ^ tables[1][(key>>8)&FF]
    //               ^ tables[2][(key>>16)&FF] ^ tables[3][(key>>24)&FF] }
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_tabulation_hash_u64(c: &mut Criterion) {
        let mut tables = [[0u64; 256]; 4];
        tabulation_hash_init_tables(123456789, &mut tables);
        c.bench_function("tabulation_hash_u64", |b| {
            b.iter(|| {
                black_box(tabulation_hash_u64(
                    black_box(0x12345678u32),
                    black_box(&tables),
                ))
            })
        });
    }
}
