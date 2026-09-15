//! Aggregate Patterns: Higher-order constructs built from branchless primitives.

pub mod autonomic_arena;
pub mod bit_transcoder;
pub mod bloom_scan;
pub mod deterministic_mpmc;
pub mod integrity_receipt;
pub mod policy_dfa;
pub mod register_sql;
pub mod swar_petri;
pub mod wait_free_multicast;
pub mod wcet_fiber;

// Advanced Abstractions
pub mod bitonic_pq;
pub mod chacha_sponge;
pub mod consensus_bft;
pub mod hazard_shield;
pub mod hierarchical_time_wheel;
pub mod matrix_lru;
pub mod radix_trie;
pub mod swar_quotient;
pub mod time_wheel;

pub use autonomic_arena::AutonomicExhaustionArena;
pub use bit_transcoder::BitTranscoder;
pub use bloom_scan::BloomScanPipeline;
pub use deterministic_mpmc::LockFreeMpmcRing;
pub use hierarchical_time_wheel::HierarchicalTimeWheel;
pub use integrity_receipt::DeterministicSubstrateReceipt;
pub use policy_dfa::ConstantShapePolicyDfa;
pub use register_sql::RegisterEngine;
pub use swar_petri::PriorityPetriEngine;
pub use wait_free_multicast::BoundedSpscMulticast;
pub use wcet_fiber::WcetFiber;

// Advanced Exports
pub use bitonic_pq::BitonicPriorityQueue8;
pub use chacha_sponge::ChaChaSponge;
pub use consensus_bft::FixedConsensus;
pub use hazard_shield::HazardShield;
pub use matrix_lru::MatrixLru;
pub use radix_trie::RadixTrieNode;
pub use swar_quotient::SwarQuotientFilter;
pub use time_wheel::TimeWheel;

#[cfg(test)]
mod tests;
