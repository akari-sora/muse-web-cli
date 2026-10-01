import argparse
import re
import tomllib
from pathlib import Path

from muse_web_cli import __version__
from muse_web_cli.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SKILL = (ROOT / "skills" / "muse-web-cli" / "SKILL.md").read_text(encoding="utf-8")
URLS = (
    "https://gitlab.com/aa22396584/trinity-cli",
    "https://gitlab.com/aa22396584/chatgpt-dot-cli",
    "https://gitlab.com/aa22396584/grok-bot-cli",
    "https://gitlab.com/aa22396584/muse-web-cli",
)


def test_every_command_has_help_and_is_documented():
    parser = build_parser()
    help_text = parser.format_help()
    assert "examples:" in help_text
    for flag in ("--json", "--port", "--backend", "--autostart", "--chrome"):
        assert flag in help_text
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    assert subparsers.choices
    for name, sub in subparsers.choices.items():
        assert name in README
        assert name in SKILL
        text = sub.format_help()
        assert name in text
        assert len(text.strip()) > 40
        for action in sub._actions:
            if action.help in {None, argparse.SUPPRESS}:
                continue
            assert str(action.help).strip()


def test_readme_links_the_family_and_the_credential_schema():
    for url in URLS:
        assert url in README
    for key in ("base_url", "timeout_s", "bearer", "header_name", "endpoints"):
        assert key in README
        assert key in SKILL or key in ("header_name",)
    assert "trinity-cli" in SKILL
    assert "xvfb-run" in README
    assert "PowerShell" in README


def test_version_changelog_and_install_pins_agree():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert __version__ == version
    newest = re.search(r"^## \[([^\]]+)\]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert newest and newest.group(1) == version
    assert set(re.findall(r"muse-web-cli\.git@v([^\"\s]+)", README)) == {version}
    assert f"muse-web-cli {version}" in README
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert f'name = "muse-web-cli"\nversion = "{version}"' in lock


def test_docs_say_where_the_token_goes():
    for text in (README, SKILL, build_parser().format_help()):
        assert "muse-credential" in text
        assert "mode 600" in text
    for stale in ("does not export the login", "也不會把登入狀態另存一份", "never extracts cookies or tokens"):
        assert stale not in README
