# AI GitHub workflows

Reusable GitHub Actions sources, with no instruction budget. This directory does not activate Actions. The portable Markdown workflows remain in [workflows](../../workflows/README.md).

## Gemini release proposal and draft

Copy [gemini-release.yml](gemini-release.yml) and [gemini_release.py](gemini_release.py) to `.github/workflows/` on the target repository's default branch, and add `GEMINI_API_KEY` as an Actions secret. The dispatch job in `.github/workflows/distribute-arena.yml` copies both files, `nemoe7/daedalus` by default, with the `CLANKERS_DIST_PAT` secret. That token needs Workflows write access because the copy changes `.github/workflows/`.

Run **Gemini Release Draft** with no proposal run ID to propose a release. The proposal shows the version, SHA and notes in the Actions summary, and it creates no tag or release. Review the notes and target, then run the workflow again with the successful proposal run ID. That run reuses the saved notes and does not call Gemini.

- The baseline is the latest published release reachable from the target. The first release is `v0.1.0`, and SemVer decides the bump. The `override` input forces `major`, `minor`, `patch` or `none`, and `promote_to_stable` takes `1.0.0` from a published `0.y.z`.
- The `evidence` input selects commits and diffs (default) or commit messages alone.
- The job has a 60-minute timeout. Gemini requests send repository history to Google and can incur API costs.

## Check

```cmd
python -m pytest github\workflows\test_gemini_release.py
```

The check uses temporary Git history and mocked API responses. It needs no API keys and creates no releases.
