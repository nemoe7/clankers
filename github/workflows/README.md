# AI GitHub workflows

Reusable GitHub Actions sources, with no instruction budget. This directory does not activate Actions.

## Gemini release proposal and draft

Copy [gemini-release.yml](gemini-release.yml), [gemini_release.py](gemini_release.py) and [gemini-release-evidence.json](gemini-release-evidence.json) to `.github/workflows/` on the target repository's default branch. Replace `CHANGE-ME/**` with the target product paths, and add `GEMINI_API_KEY` as an Actions secret. Keep the policy target-owned: distribution does not synchronize it.

Run **Gemini Release Draft** with no proposal run ID to propose a release. The proposal shows the version, SHA, and notes in the Actions summary, and it creates no tag or release. Review the notes and target, then run the workflow again with the successful proposal run ID. That run reuses the saved notes and does not call Gemini.

- The baseline is the latest published release reachable from the target (`v0.1.0` first, with SemVer deciding the bump). The `override` input forces `major`, `minor`, `patch`, or `none`, and `promote_to_stable` takes `1.0.0` from a published `0.y.z`.
- The `evidence` input selects commits and diffs (default) or commit messages alone.
- The target-owned evidence policy has `include` and `exclude` glob lists where exclude wins. A nonempty include rejects an unknown path before Gemini receives evidence (`include: []` selects a blacklist-only policy).
- The summary lists selected and omitted commit IDs and reason codes. A mixed commit sends only its selected paths.
- The job has a 60-minute timeout. Gemini requests send repository history to Google and can incur API costs.

HTTP 503 permits two more attempts per model per request. Its wait starts at 5 seconds, doubles to a 60-second cap, and adds up to 5 seconds of random delay. The 300-second request deadline caps waits and API timeouts, while HTTP 429 retry hints and safety margins stay unchanged.

## Check

```cmd
python -m pytest github\workflows\test_gemini_release.py
```

The check uses temporary Git history and mocked API responses. It needs no API keys and creates no releases.
