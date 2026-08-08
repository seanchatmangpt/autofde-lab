
# Wrapper for user-provided evaluator function
import autofde_lab.hub.solver.openevolve.evaluator_builder as evaluator_builder_module

def evaluate(program_path):
    '''Wrapper for auto-generated evaluator function from user parameters.

    Based on autofde_lab.hub.solver.openevolve.evaluator_builder.evaluate with pre-filled args.

    '''
    user_evaluator = getattr(evaluator_builder_module, '_openevolve_evaluator_cdc59421')
    return user_evaluator(program_path)
