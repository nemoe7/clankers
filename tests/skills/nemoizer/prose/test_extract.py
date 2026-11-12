"""nemoizer prose extraction tests."""

import assertions
import config
import prose.extract
import prose.rotate
from conftest import run


def test_block_comment_prose_keeps_its_source_line_and_exclusion(tmp_path):
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.js"
  prefix = "\n" * 4
  source.write_text(prefix + "/*\n * " + sentence + "\n */\n", encoding="utf-8")
  first = source.read_text(encoding="utf-8").splitlines().index(" * " + sentence) + 1
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert f"example.js:{first}: [STE200]" in result.stdout
  source.write_text(
    prefix + "/*\n * " + sentence + " nonemo: STE200\n * " + sentence + "\n */\n",
    encoding="utf-8",
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert f"example.js:{first}: [STE200]" not in result.stdout
  assert f"example.js:{first + 1}: [STE200]" in result.stdout


def test_default_prose_checks_extract_python_comments_not_literals(tmp_path):
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.py"
  source.write_text(f'value = "{sentence}"\n', encoding="utf-8")
  assert run(cwd=tmp_path).returncode == 0
  source.write_text(f'value = "{sentence}"\n# {sentence}\n', encoding="utf-8")
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "example.py:2: [STE200]" in result.stdout  # nonemo: NMT100
  assert "example.py:1:" not in result.stdout


def test_escaped_docstring_newline_uses_a_physical_source_line(tmp_path):
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.py"
  for prefix in ("Short.\\n", "\\n", "\\nShort.\\n"):
    source.write_text('"""' + prefix + sentence + '"""\n', encoding="utf-8")
    result = run(cwd=tmp_path)
    assert result.returncode == 1, result.stderr
    assert "example.py:1: [STE200]" in result.stdout  # nonemo: NMT100


def test_javascript_parsers_count_crlf_as_one_line_break():
  source = "// one\r\n// two\r\nassert.equal(panel.width, 320);\r\n"
  assert [first for _, first, _ in prose.extract.javascript_comments(source)] == [1, 2]
  assert [span[0][0] for span in prose.extract.javascript_comment_spans(source)] == [
    1,
    2,
  ]
  pairs = assertions.javascript_pairs(source)["pairs"]
  assert [pair["line"] for pair in pairs] == [3]


def test_markdown_trailing_newline_keeps_source_lines_and_local_exclusions(tmp_path):
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "note.md"
  lines = [
    "# Note",
    "",
    "Short.",
    "",
    sentence,
    "",
    sentence + " <!-- nonemo: STE200 -->",
  ]
  source.write_text("\n".join(lines) + "\n", encoding="utf-8")
  result = run(cwd=tmp_path)
  first = lines.index(sentence) + 1
  second = len(lines)
  assert result.returncode == 1, result.stderr
  assert f"note.md:{first}: [STE200]" in result.stdout
  assert f"note.md:{second}: [STE200]" not in result.stdout


def test_source_extractors_skip_module_and_yaml_data_literals(tmp_path):
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  for filename, code in (
    ("example.mjs", 'const value = "' + sentence + '";\n'),
    ("example.yaml", 'value: "' + sentence + '"\n'),
  ):
    source = tmp_path / filename
    source.write_text(code, encoding="utf-8")
    result = run(str(source), cwd=tmp_path)
    assert result.returncode == 0, (filename, result.stdout, result.stderr)


def test_sql_dbml_env_and_jinja_comment_extractors_and_ste903_guard(tmp_path):
  schema_sql = tmp_path / "schema.sql"
  schema_sql.write_text(
    "-- The service reads and writes rows.\n"
    "-- Start; stop.\n"
    "CREATE TABLE items (id INTEGER PRIMARY KEY, kind TEXT, repository TEXT);\n",
    encoding="utf-8",
  )
  schema_dbml = tmp_path / "schema.dbml"
  schema_dbml.write_text(
    "// The table is disabled and locked.\n"
    "// First clause; second clause.\n"
    "Table items {\n"
    "  id int [pk]\n"
    "  kind varchar\n"
    "}\n",
    encoding="utf-8",
  )
  env_example = tmp_path / ".env.example"
  env_example.write_text(
    "# Keep one token per line.\n"
    "# First token; second token.\n"
    "KIND=production\n"
    "REPOSITORY_URL=https://example.com\n",
    encoding="utf-8",
  )
  template_jinja = tmp_path / "view.jinja"
  template_jinja.write_text(
    "{# Render the card header. #}\n"
    "{# First part; second part. #}\n"
    "<div>{{ item.kind }}; {{ item.repository }}</div>\n",
    encoding="utf-8",
  )
  template_jinja_html = tmp_path / "card.jinja.html"
  template_jinja_html.write_text(
    "{# Name the source in the summary. #}\n"
    "<div>{{ item.kind }}; {{ item.name }}</div>\n",
    encoding="utf-8",
  )
  res = run(
    "--no-config",
    str(schema_sql),
    str(schema_dbml),
    str(env_example),
    str(template_jinja),
    str(template_jinja_html),
    cwd=tmp_path,
  )
  assert res.returncode == 1, res.stderr
  assert f"{schema_sql}:2: [STE100]" in res.stdout
  assert f"{schema_sql}:3:" not in res.stdout
  assert f"{schema_dbml}:2: [STE100]" in res.stdout
  assert f"{schema_dbml}:5:" not in res.stdout
  assert f"{env_example}:2: [STE100]" in res.stdout
  assert f"{env_example}:3:" not in res.stdout
  assert f"{template_jinja}:2: [STE100]" in res.stdout
  assert f"{template_jinja}:3:" not in res.stdout
  assert f"{template_jinja_html}:1: [NMO901]" in res.stdout
  assert f"{template_jinja_html}:2:" not in res.stdout
  assert "STE903" not in res.stdout
  assert "NMO100" not in res.stdout
  assert (
    prose.rotate.rotate(
      "- Name a relationship and the sheet names the single size, keeping role names."
    )
    == "- Specify a relationship and the sheet specifies the single size, keeping role names."
  )


def test_workflow_name_spans_identifier_boundaries_and_mixed_determiner_lists(tmp_path):
  wf_dir = tmp_path / ".github" / "workflows"
  wf_dir.mkdir(parents=True)
  wf = wf_dir / "ci.yml"
  wf.write_text(
    "name: Build the image\n"
    "on: push\n"
    "jobs:\n"
    "  deploy:\n"
    "    name: Deploy the release\n"
    "    runs-on: ubuntu-latest\n"
    "    environment: { name: github-pages }\n"
    "    env:\n"
    "      name: the-env-var\n"
    "      repo_ref: ${{ github.repository }}\n"
    "    steps:\n"
    "      - name: Checkout the code\n"
    "        uses: actions/checkout@v4\n"
    "        with:\n"
    "          name: the-artifact\n"
    "          repository: ${{ github.repository }}\n"
    "      - name: build-slug\n"
    "        run: echo ok\n",
    encoding="utf-8",
  )
  wf_res = run(str(wf), cwd=tmp_path)
  assert wf_res.returncode == 0, wf_res.stderr
  for hit_ln in (1, 5, 12):
    assert f"{wf.name}:{hit_ln}: [NMO902]" in wf_res.stdout
  assert "NMO901" not in wf_res.stdout
  for skipped_ln in (7, 9, 10, 15, 16, 17):
    assert f"ci.yml:{skipped_ln}:" not in wf_res.stdout

  py_file = tmp_path / "mod.py"
  py_file.write_text(
    '""" Process items.\n\n'
    ":param repository: Target repo.\n"
    ":param picker: Widget selector.\n"
    '"""\n'
    "def run_task(user_repository, pick_mode):\n"
    '  url = "https://example.com/repository/pick"\n'
    "  picked = pick_mode  # Pick a file from the repository.\n"
    "  return picked, user_repository, url\n",
    encoding="utf-8",
  )
  md_file = tmp_path / "doc.md"
  md_file.write_text(
    "Use `pick_mode` and `github.repository` or `/repository/pick` in `user_repository`.\n"
    "Also skip snake_pick, $pick, cherry-pick, and ${{ github.repository }}.\n"
    "Pick a file from the repository.\n",
    encoding="utf-8",
  )
  id_res = run(str(py_file), str(md_file), cwd=tmp_path)
  assert id_res.returncode == 0, id_res.stderr
  assert f"{py_file}:8: [NMO901]" in id_res.stdout
  for safe_py_ln in (1, 3, 4, 6, 7, 9):
    assert f"{py_file}:{safe_py_ln}: [NMO901]" not in id_res.stdout
  assert f"{md_file}:3: [NMO901]" in id_res.stdout
  assert f"{md_file}:1: [NMO901]" not in id_res.stdout
  assert f"{md_file}:2: [NMO901]" not in id_res.stdout

  mixed_py = tmp_path / "mixed.py"
  mixed_py.write_text(
    "# The image ships the package, its config, the hooks, and the lock.\n"
    "# Keep the output in the cache directory after each build pass.\n"
    "x = 1\n",
    encoding="utf-8",
  )
  mixed_res = run(str(mixed_py), cwd=tmp_path)
  assert mixed_res.returncode == 0, mixed_res.stderr
  assert "NMO902" not in mixed_res.stdout

  slash_or = tmp_path / "slash_or.md"
  slash_or.write_text(
    "| Component / Property or Recipe | Reason |\n"
    "| --- | --- |\n"
    "| Button or Input / Select | Validated |\n"
    "| Component, Property, or Recipe | Consistent |\n"
    "| Component / Property / Recipe | Consistent |\n",
    encoding="utf-8",
  )
  slash_res = run(str(slash_or), cwd=tmp_path)
  assert slash_res.returncode == 1, slash_res.stderr
  assert f"{slash_or.name}:1: [NMO003]" in slash_res.stdout
  assert f"{slash_or.name}:3: [NMO003]" in slash_res.stdout
  assert f"{slash_or.name}:4:" not in slash_res.stdout
  assert f"{slash_or.name}:5:" not in slash_res.stdout
