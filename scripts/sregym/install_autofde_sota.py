from __future__ import annotations

import argparse
import shutil
from pathlib import Path


AGENT_STANZA = """
  - name: autofde-sota
    kickoff_command: python -m clients.autofde.driver
    kickoff_workdir: .
    kickoff_env:
      PYTHONPATH: "../src"
    install_script: null
    agent_version: SRE-SIG-001
    container_isolation: false
""".rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sregym-dir", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    source = repo / "src" / "autofde_lab" / "sregym_sota"
    target_root = Path(args.sregym_dir).resolve()
    target = target_root / "clients" / "autofde"
    target.mkdir(parents=True, exist_ok=True)
    (target / "__init__.py").write_text("")
    copied = target / "autofde_sota"
    if copied.exists():
        shutil.rmtree(copied)
    shutil.copytree(source, copied)
    (target / "driver.py").write_text(
        "from clients.autofde.autofde_sota.agent import main\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )

    agents = target_root / "agents.yaml"
    text = agents.read_text()
    if "name: autofde-sota" not in text:
        agents.write_text(text.rstrip() + "\n" + AGENT_STANZA)
    print(f"installed autofde-sota from {source} into {target_root}")


if __name__ == "__main__":
    main()
