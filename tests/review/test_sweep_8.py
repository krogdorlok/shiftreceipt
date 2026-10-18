"""The judge README must contain the actual agent address required by M5."""
import re
from pathlib import Path


def test_readme_has_agent_address_not_placeholder():
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()
    assert re.search(r"\bagent1[0-9a-z]{30,}\b", readme), "README still has an agent address placeholder"
