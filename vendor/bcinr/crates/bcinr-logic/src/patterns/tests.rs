//! Integration tests for Refined Aggregate Patterns.
#![allow(clippy::module_inception)]

#[cfg(test)]
mod tests {
    use crate::models::petri::KBitSet;
    use crate::patterns::*;

    /// Core pattern primitives: pipeline, petri, mpmc, arena, transcoder.
    #[test]
    fn test_core_patterns() {
        // BloomScanPipeline
        let pipeline = BloomScanPipeline::new(0x1234567890ABCDEF);
        let buffer = [b'a'; 64];
        let _ = pipeline.process_64(&buffer, b'a');

        // PriorityPetriEngine
        let initial = KBitSet { words: [1; 1] };
        let inputs = [KBitSet { words: [1; 1] }];
        let outputs = [KBitSet { words: [2; 1] }];
        let mut engine = PriorityPetriEngine::new_checked(initial, inputs, outputs).unwrap();
        let mask = engine.step();
        assert_eq!(mask & 1, 1);
        assert_eq!(engine.state.current.words[0], 2);

        // LockFreeMpmcRing
        let ring = LockFreeMpmcRing::<u32, 16>::new_checked().unwrap();
        assert_eq!(ring.push_t1(42), !0);
        let (val, ok) = ring.pop_t1();
        assert_eq!(ok, !0);
        assert_eq!(val, Some(42));

        // AutonomicExhaustionArena
        let mut arena = AutonomicExhaustionArena::new(1024, 100);
        let (off, success) = arena.alloc_aligned_t1(50);
        assert_eq!(success, !0);
        assert_eq!(off, 0);
        assert_eq!(arena.arena.offset, 56);

        // BitTranscoder
        let transcoder = BitTranscoder::new(0x0F0F0F0F0F0F0F0F, 0xF0F0F0F0F0F0F0F0);
        let _ = transcoder.transcode(0x1234567890ABCDEF);

        // ConstantShapePolicyDfa
        static TABLE: [usize; 2 * 256] = [0; 2 * 256];
        let dfa = ConstantShapePolicyDfa::new_checked(&TABLE, 256, 2, 0, 0).unwrap();
        assert_eq!(dfa.run(b"abc", 0), 0);

        // DeterministicSubstrateReceipt
        let mut receipt = DeterministicSubstrateReceipt::new();
        receipt.record(1, 1, 2);
        let h1 = receipt.finalize();
        receipt.record(1, 3, 4);
        let h2 = receipt.finalize();
        assert_ne!(h1, h2);
        assert_eq!(receipt.steps, 2);

        // BoundedSpscMulticast
        let mut multicast = BoundedSpscMulticast::<4>::new_checked().unwrap();
        assert_eq!(multicast.broadcast_partial(), 0xF);

        // WcetFiber
        let mut fiber = WcetFiber::<3>::new();
        let _ = fiber.execute_budget_fixed(&[1, 2, 3]);
        assert_eq!(fiber.instruction_pointer, 3);

        // RegisterEngine
        let mut data = [8, 7, 6, 5, 4, 3, 2, 1];
        assert_eq!(RegisterEngine::sort_and_filter(&mut data, 5), 0x0F);
    }

    /// Advanced abstraction patterns: LRU, sponge, quotient, priority-queue, hazard, trie, BFT, wheel.
    #[test]
    fn test_advanced_patterns() {
        // MatrixLru
        let mut lru = MatrixLru::<4>::new();
        lru.access(0);
        lru.access(1);
        assert_eq!(lru.find_lru(), 2);

        // ChaChaSponge
        let mut sponge = ChaChaSponge::new([0; 4]);
        sponge.absorb(0x1234);
        assert_ne!(sponge.squeeze(), 0);

        // SwarQuotientFilter
        let mut q = SwarQuotientFilter::<4>::new();
        assert!(q.insert(0, 0xAB));
        assert!(q.contains(0, 0xAB));

        // BitonicPriorityQueue8
        let mut pq = BitonicPriorityQueue8::new();
        pq.push(10);
        pq.push(5);
        let (v, _) = pq.pop();
        assert_eq!(v, 5);

        // HazardShield
        let shield = HazardShield::<4>::new();
        shield.protect(0, 0xDEAD);
        assert_ne!(shield.is_shielded(0xDEAD), 0);

        // RadixTrieNode
        let mut node = RadixTrieNode::<8>::new();
        node.bitmap[1] |= 1u64.wrapping_shl(97 - 64);
        node.children[0] = 42;
        let (idx, _) = node.lookup(b'a');
        assert_eq!(idx, 42);

        // FixedConsensus
        let mut bft = FixedConsensus::<2>::new();
        bft.vote(0);
        assert_eq!(bft.is_reached(), 0);
        bft.vote(1);
        assert_ne!(bft.is_reached(), 0);

        // TimeWheel
        let mut wheel = TimeWheel::<4>::new();
        wheel.schedule(1, 0);
        assert_eq!(wheel.tick(), 0);
        assert_eq!(wheel.tick(), 1);
    }
}
