/* Copyright (c) AIRBUS and its affiliates.
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
#include "successor_generator.hh"
#include "task.hh"

#include "../timed_effect.hh"

#include "../operator.hh"

namespace skdecide {

namespace pddl {

SuccessorGenerator::SuccessorGenerator(const Task &task) : _task(task) {}

std::vector<Successor>
SuccessorGenerator::get_successors(const State &state,
                                   const GroundAction &action) const {
  // Unified action ids: ids below actions().size() address instantaneous
  // actions; ids at or above it address durative actions (offset by the
  // instantaneous count) as classical relaxations -- the ApplicableActions-
  // Generator emits them from the applicable_da_N rules with exactly this
  // offset, and TimedEffectMode::All applies their at-start and at-end
  // effects in one step.
  const auto num_actions = static_cast<int>(_task.actions().size());
  const Effect::Ptr effect = [this, &action, num_actions]() -> Effect::Ptr {
    if (action.action_id < num_actions) {
      return _task.actions().at(action.action_id)->get_effect();
    }
    return _task.durative_actions()
        .at(action.action_id - num_actions)
        ->get_effect();
  }();
  if (!effect) {
    return {{state.copy(), 1.0}};
  }

  auto outcomes = effect->apply(state, _task, action.binding);
  std::vector<Successor> result;
  result.reserve(outcomes.size());
  for (auto &[prob, s] : outcomes) {
    result.push_back({std::move(s), prob});
  }
  return result;
}

} // namespace pddl

} // namespace skdecide
