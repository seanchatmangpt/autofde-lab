import os

from autofde_lab import Domain
from autofde_lab.builders.domain import (
    DeterministicInitialized,
    FullyObservable,
    Goals,
    Initializable,
    Sequential,
    SingleAgent,
    UnrestrictedActions,
)

template_dir = f"{os.path.dirname(__file__)}/templates"
DOMAIN_MODULE_PLACEHOLDER = "{{domain_module}}"
DOMAIN_CLS_PLACEHOLDER = "{{domain_cls}}"


class UnsupportedDomainTraitsError(NotImplementedError):
    """No program template exists for the given domain characteristics."""


def build_initial_program(
    domain_cls: type[Domain], include_rollout: bool = True
) -> str:
    domain_module = domain_cls.__module__
    domain_cls_name = domain_cls.__name__

    code = ""
    if issubclass(domain_cls, Sequential) and issubclass(domain_cls, SingleAgent):
        if issubclass(domain_cls, FullyObservable):
            if issubclass(domain_cls, UnrestrictedActions):
                template_path = f"{template_dir}/initial_program_sequential_singleagent_unrestrictedactions_fullyobservable.py.template"
            else:
                template_path = f"{template_dir}/initial_program_sequential_singleagent_fullyobservable.py.template"
        else:
            if issubclass(domain_cls, UnrestrictedActions):
                template_path = f"{template_dir}/initial_program_sequential_singleagent_unrestrictedactions.py.template"
            else:
                template_path = (
                    f"{template_dir}/initial_program_sequential_singleagent.py.template"
                )
    else:
        raise UnsupportedDomainTraitsError(
            "No initial program template defined for this domain characteristics."
        )

    with open(template_path, "r") as f:
        code += (
            f.read()
            .replace(DOMAIN_MODULE_PLACEHOLDER, domain_module)
            .replace(DOMAIN_CLS_PLACEHOLDER, domain_cls_name)
        )

    if include_rollout:
        if (
            issubclass(domain_cls, Sequential)
            and issubclass(domain_cls, SingleAgent)
            and issubclass(domain_cls, Initializable)
        ):
            if issubclass(domain_cls, FullyObservable) and issubclass(
                domain_cls, DeterministicInitialized
            ):
                if issubclass(domain_cls, UnrestrictedActions):
                    rollout_template_path = f"{template_dir}/rollout_sequential_singleagent_deterministicinitialized_fullyobservable_unrestrictedactions.py.template"
                else:
                    rollout_template_path = f"{template_dir}/rollout_sequential_singleagent_deterministicinitialized_fullyobservable.py.template"
            else:
                if issubclass(domain_cls, UnrestrictedActions):
                    rollout_template_path = f"{template_dir}/rollout_sequential_singleagent_initializable_unrestrictedactions.py.template"
                else:
                    rollout_template_path = f"{template_dir}/rollout_sequential_singleagent_initializable.py.template"
        else:
            raise UnsupportedDomainTraitsError(
                "No rollout template defined for this domain characteristics."
            )

        with open(rollout_template_path, "r") as f:
            code += f.read().replace(DOMAIN_CLS_PLACEHOLDER, domain_cls_name)

        if issubclass(domain_cls, Goals):
            if issubclass(domain_cls, FullyObservable):
                rollout_addon_template_path = (
                    f"{template_dir}/rollout_addon_goal_fullyobservable.py.template"
                )
            else:
                rollout_addon_template_path = (
                    f"{template_dir}/rollout_addon_goal.py.template"
                )
            with open(rollout_addon_template_path, "r") as f:
                code += f.read()
    return code
