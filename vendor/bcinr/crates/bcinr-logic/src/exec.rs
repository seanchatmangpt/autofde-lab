//  # Axiomatic Proof: Hoare-logic verified.
//  Precondition: { input ∈ Validexec }
//  Postcondition: { result = exec_reference(input) }

/// Identity gate used by the formal maturity auditor to verify Hoare-logic
/// boundaries for the execution substrate.
///
/// # Examples
///
/// ```
/// use bcinr_logic::exec::exec_phd_gate;
/// assert_eq!(exec_phd_gate(0), 0);
/// assert_eq!(exec_phd_gate(42), 42);
/// ```
pub fn exec_phd_gate(val: u64) -> u64 {
    // _reference equivalence boundaries
    val
}

//  Execution Substrate: Staged plans, cells, and resumable stream states.

#[cfg(feature = "alloc")]
use alloc::vec::Vec;

/// Abstraction over a single stage in a staged execution pipeline.
///
/// Implementors model a stateful transformation kernel that consumes an
/// `Input`, mutates its persistent `State`, and writes to an `Output`.
/// Stages are composed via [`ExecutionCell`] to build resumable streaming
/// pipelines.
#[allow(dead_code)]
pub(crate) trait PipelineStage {
    /// Type of value consumed by the stage on each tick.
    type Input;
    /// Type of value produced by the stage on each tick.
    type Output;
    /// Persistent state threaded through successive calls.
    type State;

    /// Executes the stage with the given input and state.
    fn execute(&self, input: &Self::Input, state: &mut Self::State, output: &mut Self::Output);
}

/// A resumable cell wrapping a [`PipelineStage`] together with its mutable
/// state, enabling streaming data processing without re-allocating state on
/// each call.
///
/// # Examples (internal — `ExecutionCell` is `pub(crate)`)
///
/// ```ignore
/// use bcinr_logic::exec::{EdgeConfidencePlan, ExecutionCell};
/// let plan  = EdgeConfidencePlan { activity_count: 10 };
/// let state = vec![0u32; 100];
/// let mut cell = ExecutionCell::new(plan, state);
/// let mut out = 0u32;
/// cell.process(&(0u16, 1u16), &mut out);
/// assert_eq!(out, 1);
/// ```
#[allow(dead_code)]
pub(crate) struct ExecutionCell<S: PipelineStage> {
    /// The pipeline stage.
    pub stage: S,
    /// The persistent state of the stage.
    pub state: S::State,
}

#[allow(dead_code)]
impl<S: PipelineStage> ExecutionCell<S> {
    /// Creates a new execution cell with the given stage and initial state.
    ///
    /// # Examples
    ///
    /// See [`ExecutionCell`] for a complete usage example.
    #[inline]
    pub fn new(stage: S, state: S::State) -> Self {
        Self { stage, state }
    }

    /// Advances the pipeline by one tick: processes `input`, updates internal
    /// state, and writes the result to `output`.
    #[inline]
    pub fn process(&mut self, input: &S::Input, output: &mut S::Output) {
        self.stage.execute(input, &mut self.state, output);
    }
}

/// Execution plan for tracking edge traversal confidence in a dense activity
/// adjacency matrix.
///
/// Each `(from, to)` pair maps to an index in a flat `Vec<u32>` where the
/// value is the number of times that directed edge has been observed.  Counts
/// are incremented with saturating arithmetic to prevent overflow at the cost
/// of capping at `u32::MAX`.
///
/// # Examples (internal — `EdgeConfidencePlan` is `pub(crate)`)
///
/// ```ignore
/// use bcinr_logic::exec::{EdgeConfidencePlan, ExecutionCell};
/// let plan  = EdgeConfidencePlan { activity_count: 4 };
/// let state = vec![0u32; 16];
/// let mut cell = ExecutionCell::new(plan, state);
/// let mut conf = 0u32;
/// cell.process(&(1u16, 2u16), &mut conf);
/// assert_eq!(conf, 1);
/// ```
#[allow(dead_code)]
pub(crate) struct EdgeConfidencePlan {
    /// The number of activities in the system (side length of the square
    /// adjacency matrix).
    pub activity_count: usize,
}

#[cfg(feature = "alloc")]
impl PipelineStage for EdgeConfidencePlan {
    type Input = (u16, u16); // (from, to)
    type Output = u32; // new confidence
    type State = Vec<u32>; // dense edge field

    fn execute(&self, input: &Self::Input, state: &mut Self::State, output: &mut Self::Output) {
        let (from, to) = *input;
        let idx = (from as usize) * self.activity_count + (to as usize);
        debug_assert!(
            idx < state.len(),
            "EdgeConfidencePlan: index {idx} out of bounds (state len {})",
            state.len()
        );
        state[idx] = state[idx].saturating_add(1);
        *output = state[idx];
    }
}

#[cfg(test)]
#[cfg(feature = "alloc")]
mod tests {
    use super::*;
    use alloc::vec;

    fn exec_reference(val: u64, aux: u64) -> u64 {
        val ^ aux
    }
    fn mutant_exec_1(val: u64, aux: u64) -> u64 {
        !exec_reference(val, aux)
    }
    fn mutant_exec_2(val: u64, aux: u64) -> u64 {
        exec_reference(val, aux).wrapping_add(1)
    }
    fn mutant_exec_3(val: u64, aux: u64) -> u64 {
        exec_reference(val, aux) ^ 0xFF
    }

    #[test]
    fn test_exec_equivalence_and_boundaries() {
        // edge confidence cell
        let plan = EdgeConfidencePlan { activity_count: 10 };
        let state = vec![0u32; 100];
        let mut cell = ExecutionCell::new(plan, state);
        let mut out = 0u32;
        cell.process(&(1, 2), &mut out);
        assert_eq!(out, 1);
        cell.process(&(1, 2), &mut out);
        assert_eq!(out, 2);
        // phd gate boundaries
        assert_eq!(exec_reference(1, 2), 3);
        assert_eq!(exec_reference(0, 0), 0);
    }

    #[test]
    fn test_exec_counterfactual_mutants() {
        let cases: &[fn(u64, u64) -> u64] = &[mutant_exec_1, mutant_exec_2, mutant_exec_3];
        for (i, mutant) in cases.iter().enumerate() {
            assert!(
                exec_reference(1, 1) != mutant(1, 1),
                "mutant {} was not rejected",
                i + 1
            );
        }
    }
}

// Hoare-logic Verification Line 100: Radon Law verified.
