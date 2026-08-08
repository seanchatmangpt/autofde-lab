from unrestricted_action_maze import Maze


# EVOLVE-BLOCK-START
class Planner:
    """Random planner.

    It demonstrates the needed api, but performs poorly.

    """

    def __init__(self, domain: Maze):
        """

        Args:
            domain: the domain to solve
        """
        self.domain = domain

    def sample_action(self, state: Maze.T_state) -> Maze.T_event:
        """Sample next action for the given state.

        Pure random sampling, not using any heuristic, not leading to great results.

        Args:
            state: the current state

        Returns:
            sampled action

        """
        return self.domain.get_action_space().sample()

# EVOLVE-BLOCK-END

if __name__ == "__main__":
    # Rollout using the above planner.

    domain = Maze()
    planner = Planner(domain=domain)

    # rollout
    max_steps = 100
    nb_step = 0
    total_cost = 0
    state = domain.get_initial_state()
    while not domain.is_terminal(state) and nb_step < max_steps:
        action = planner.sample_action(state)
        next_state = domain.get_next_state(memory=state, action=action)
        value = domain.get_transition_value(
            memory=state, action=action, next_state=next_state
        )
        state = next_state
        total_cost += value.cost
        nb_step += 1

    print(f"total cost: {total_cost}")
    if domain.is_goal(state):
        print("Goal reached!")
    else:
        print("Goal not reached.")
