"""Tests for the stage runner, the `nemoize` stage, and the command line."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

from checks import budgets, cli, prose
from checks.repo import DEFAULT_ROOT, Repo

NO_NEMOIZE = tuple(stage for stage in cli.STAGES if stage[0] != "nemoize")


def test_stages_run_in_a_fixed_order_with_nemoize_last():
  assert [name for name, _ in cli.STAGES] == [
    "skills",
    "links",
    "budgets",
    "parity",
    "paths",
    "nemoize",
  ]


def test_run_stages_returns_what_each_stage_reported(tmp_path: Path, capsys):
  errors: list[str] = []
  stages = (
    ("one", lambda repo, errs: 1),
    ("two", lambda repo, errs: errs.append("bad")),
  )
  assert cli.run_stages(Repo(tmp_path), errors, stages) == {"one": 1, "two": None}
  assert errors == ["bad"]
  assert "FAIL two:" in capsys.readouterr().out


def test_stages_continue_after_a_stale_budget(monkeypatch, capsys):
  table = budgets.read_budget_table(Repo(DEFAULT_ROOT))
  row = next(iter(table))
  table[row] = (table[row][0], "999,999,999")
  monkeypatch.setattr(budgets, "read_budget_table", lambda repo: table)
  monkeypatch.setattr(cli, "STAGES", NO_NEMOIZE)

  assert cli.main([]) == 1
  output = capsys.readouterr().out
  for stage in ("skills", "links", "budgets", "parity", "paths"):
    assert f"== {stage} ..." in output
  assert "FAIL budgets:" in output
  assert f"README budget stale for {row}" in output
  assert (
    output.index("FAIL budgets:")
    < output.index("== parity ...")
    < output.index("== paths ...")
  )


def test_main_fails_on_a_stage_error_and_prints_it_once_more(monkeypatch, capsys):
  monkeypatch.setattr(
    cli, "STAGES", (("nemoize", lambda repo, errors: errors.append("rotation-data")),)
  )
  assert cli.main([]) == 1
  output = capsys.readouterr().out
  assert output.count("rotation-data") == 2


def test_main_reports_one_nemoize_stage_and_a_summary(monkeypatch, capsys):
  calls = []
  monkeypatch.setattr(
    cli,
    "STAGES",
    (
      ("skills", lambda repo, errors: 4),
      ("nemoize", lambda repo, errors: calls.append(1)),
    ),
  )
  assert cli.main([]) == 0
  output = capsys.readouterr().out
  assert calls == [1]
  assert output.count("== nemoize ...") == 1
  assert (
    "4 skills, README measurements, refs/live parity and nemoize checked." in output
  )


def test_update_failure_stops_before_any_stage(tmp_path: Path, monkeypatch, capsys):
  (tmp_path / "README.md").write_text("# No table\n", encoding="utf-8")
  ran = []
  monkeypatch.setattr(cli, "STAGES", (("skills", lambda repo, errors: ran.append(1)),))
  assert cli.main(["--update"], repo=Repo(tmp_path)) == 1
  assert ran == []
  assert "instruction-budget" in capsys.readouterr().out


def test_update_flag_rebuilds_the_table_first(tmp_path: Path, monkeypatch, capsys):
  (tmp_path / "rules").mkdir()
  (tmp_path / "rules/CORE.md").write_text("hello world", encoding="utf-8")
  (tmp_path / "README.md").write_text(
    "| File | Measure | Current |\n| --- | --- | --- |\n| `old.md` | `o200k_base` | 1 `tok` |\n",
    encoding="utf-8",
  )
  monkeypatch.setattr(cli, "STAGES", ())
  assert cli.main(["--update"], repo=Repo(tmp_path)) == 0
  assert "Updated" in capsys.readouterr().out
  assert "rules/CORE.md" in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_parse_args_defaults_to_no_update():
  assert cli.parse_args([]).update is False
  assert cli.parse_args(["--update"]).update is True


def test_nemoize_stage_logs_the_command_and_reports_failure(
  tmp_path: Path, monkeypatch, capsys
):
  monkeypatch.setattr(
    prose,
    "run_logged",
    lambda command, **kwargs: SimpleNamespace(returncode=1, stdout="out", stderr="err"),
  )
  errors: list[str] = []
  prose.check_nemoize(Repo(tmp_path), errors)
  assert errors == ["nemoize failed:\nouterr"]


def test_nemoize_stage_passes_on_exit_zero(tmp_path: Path, monkeypatch):
  seen = {}

  def fake(command, **kwargs):
    seen.update(command=command, cwd=kwargs["cwd"], env=kwargs["env"])
    return SimpleNamespace(returncode=0, stdout="", stderr="")

  monkeypatch.setattr(prose, "run_logged", fake)
  errors: list[str] = []
  prose.check_nemoize(Repo(tmp_path), errors)
  assert errors == []
  assert seen["command"][1:] == [str(tmp_path / prose.NEMOIZE), "."]
  assert seen["cwd"] == tmp_path
  assert seen["env"]["PYTHONUTF8"] == "1"


def test_nemoize_scope_is_the_root_config(monkeypatch):
  import nemo_config
  import nemo_files

  config = tomllib.loads((DEFAULT_ROOT / "nemoizer.toml").read_text(encoding="utf-8"))
  for kept in (
    "!.agents/skills/README.md",
    "!rules/README.md",
    "!rules/refs/README.md",
  ):
    assert kept in config["extend-exclude"]
  monkeypatch.setattr(
    nemo_config, "ACTIVE_CONFIG", nemo_config.load_config([str(DEFAULT_ROOT)])
  )
  for path in (
    ".agents/skills/README.md",
    "rules/README.md",
    "rules/refs/README.md",
    "docs/CHANGELOG.md",
    "docs/nuu/README.md",
    "docs/nuu/CHANGELOG.md",
  ):
    assert not nemo_files.skipped(DEFAULT_ROOT / path, DEFAULT_ROOT, ())
  assert nemo_files.skipped(
    DEFAULT_ROOT / "docs/archive/CHANGELOG.md", DEFAULT_ROOT, ()
  )
  assert nemo_files.skipped(DEFAULT_ROOT / ".agents/skills/other.md", DEFAULT_ROOT, ())
  assert nemo_files.skipped(DEFAULT_ROOT / "rules/other.md", DEFAULT_ROOT, ())


def test_nemoize_stays_a_standalone_tool(tmp_path: Path):
  source = DEFAULT_ROOT / prose.NEMOIZE
  standalone = tmp_path / "standalone"
  shutil.copytree(
    source.parent, standalone, ignore=shutil.ignore_patterns("__pycache__")
  )
  result = subprocess.run(
    [sys.executable, str(standalone / source.name), "--selftest"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
    cwd=tmp_path,
  )
  assert result.returncode == 0, result.stderr


def test_child_env_preserves_the_utf8_flag():
  assert prose.CHILD_ENV.get("PYTHONUTF8") == "1"
