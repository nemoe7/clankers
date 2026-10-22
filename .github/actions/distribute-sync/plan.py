import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROFILES = (
  {
    "domain": "arena",
    "repos": (
      "nemoe7/clankers nemoe7/daedalus nemoe7/asset-tracker nemoe7/wiki "
      "nemoe7/f360 nemoe7/request-tracker nemoe7/arena-cleanup nemoe7/template"
    ),
    "rule_src": "rules/ARENA.md",
    "rule_dest": "ARENA.md",
    "skills": "arena-skill",
    "legacy": "arena-live-steering arena-preview-reporting arena-preview-steering arena-proxy arena",
  },
  {
    "domain": "gemini",
    "repos": "nemoe7/daedalus nemoe7/request-tracker",
    "files": "gemini-release.yml gemini_release.py",
  },
  {
    "domain": "nemo-ui-ux",
    "repos": "nemoe7/request-tracker nemoe7/daedalus nemoe7/clankers nemoe7/arena-cleanup",
    "skills": "nuu",
    "legacy": "nemo-ui nemo-ui-ux",
  },
  {
    "domain": "nemoizer",
    "repos": "nemoe7/request-tracker nemoe7/daedalus nemoe7/clankers nemoe7/arena-cleanup nemoe7/wiki nemoe7/template",
    "skills": "nemoizer",
  },
)
FIELDS = ("rule_src", "rule_dest", "skills", "legacy", "files")
INPUTS = {
  "arena": "ARENA_REPOS",
  "gemini": "GEMINI_REPOS",
  "nemo-ui-ux": "NEMO_UI_UX_REPOS",
  "nemoizer": "NEMOIZER_REPOS",
}
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def build_plan(overrides=None):
  overrides = overrides or {}
  if set(overrides) - set(INPUTS):
    raise ValueError("Unknown distribution domain")
  domains, targets = [], {}
  for profile in PROFILES:
    override = overrides.get(profile["domain"], "")
    if not isinstance(override, str):
      raise TypeError("Repository inputs must be strings")
    repos = (override or profile["repos"]).split()
    if not repos or any(not REPOSITORY.fullmatch(repo) for repo in repos):
      raise ValueError("Repository inputs require space-separated owner/repo names")
    domain = dict.fromkeys(FIELDS, "") | profile | {"repos": " ".join(repos)}
    domains.append(domain)
    seen = set()
    for repo in repos:
      key = repo.casefold()
      if key in seen:
        continue
      seen.add(key)
      target = targets.setdefault(
        key, dict.fromkeys(FIELDS, "") | {"repos": repo, "domains": []}
      )
      target["domains"].append(domain["domain"])
      for field in ("rule_src", "rule_dest"):
        if target[field] and domain[field] and target[field] != domain[field]:
          raise ValueError("A target has conflicting rule paths")
        target[field] = target[field] or domain[field]
      for field in ("skills", "legacy", "files"):
        target[field] = " ".join(
          dict.fromkeys(target[field].split() + domain[field].split())
        )
  return {"domains": domains, "targets": list(targets.values())}


def push_targets(targets, script, environment):
  if not isinstance(targets, list) or not targets:
    raise ValueError("The target plan must be a nonempty array")
  seen = set()
  for target in targets:
    if not isinstance(target, dict) or set(target) != {"repos", "domains", *FIELDS}:
      raise ValueError("The target plan fields are invalid")
    if any(not isinstance(target[field], str) for field in ("repos", *FIELDS)):
      raise ValueError("Target fields must be strings")
    if not REPOSITORY.fullmatch(target["repos"]) or target["repos"].casefold() in seen:
      raise ValueError("Each target requires one unique owner/repo name")
    domains = target["domains"]
    if (
      not isinstance(domains, list)
      or not domains
      or any(not isinstance(domain, str) or domain not in INPUTS for domain in domains)
    ):
      raise ValueError("Target domains are invalid")
    seen.add(target["repos"].casefold())
  failed = False
  for target in targets:
    env = environment | {
      "REPOS_FALLBACK": "",
      "SKILL_ROOT": "skills",
      "SKILL_DEST_ROOT": ".agents/skills",
      "SRC_ROOT": "github/workflows",
      "DEST_ROOT": ".github/workflows",
      "VALIDATE_ONLY": "false",
      "GITHUB_ACTION_PATH": str(script.parent),
    }
    env.update({field.upper(): target[field] for field in ("repos", *FIELDS)})
    result = subprocess.run(["bash", str(script)], env=env, check=False)
    failed |= result.returncode != 0
  return int(failed)


def main():
  if sys.argv[1:] == ["--push"]:
    targets = json.loads(os.environ["TARGETS_JSON"])
    return push_targets(targets, Path(__file__).with_name("sync.sh"), dict(os.environ))
  if sys.argv[1:]:
    raise ValueError("Expected no argument or --push")
  plan = build_plan(
    {domain: os.environ.get(name, "") for domain, name in INPUTS.items()}
  )
  with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
    output.write("matrix=" + json.dumps({"include": plan["domains"]}) + "\n")
    output.write("targets=" + json.dumps(plan["targets"]) + "\n")
  return 0


if __name__ == "__main__":
  try:
    raise SystemExit(main())
  except (OSError, ValueError, TypeError, KeyError) as error:
    print(f"::error::{error}", file=sys.stderr)
    raise SystemExit(1)
