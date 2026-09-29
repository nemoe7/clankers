# AI GitHub workflows

Reusable GitHub Actions sources, with no instruction budget. This directory does not activate Actions. The portable Markdown workflows remain in [workflows](../../workflows/README.md).

## Gemini release proposal and draft

Copy two files to `.github/workflows/` on the target repository's default branch: [gemini-release.yml](gemini-release.yml) and [gemini_release.py](gemini_release.py). The Python file contains the prompts and the release template. The check script stays in this repository.

Add `GEMINI_API_KEY` as an Actions secret. Run **Gemini Release Draft** from the default branch with no proposal run ID to propose a release. The model defaults to [`gemini-3.5-flash-lite`](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite). The workflow needs Contents write and Actions read permissions. The proposal run creates **no tag or release**. It shows the version, SHA and notes in the Actions summary. It uploads `gemini-release-proposal`. Review the notes and target. Run the workflow again with the **successful proposal run ID** to create the tag and draft. This run uses the saved notes and does not call Gemini. An expired artifact needs a new proposal. Use a new dispatch, not a proposal rerun: approval rejects rerun proposal IDs. Approval retries can reuse the original proposal ID.

The target defaults to the default-branch commit checked out at dispatch. You can supply a full commit SHA reachable from the default branch. The script does not execute target code. Default-branch workflow code and its writers must be trusted. The baseline is the latest published release reachable from the target, including prereleases and excluding drafts. With no published release, input includes all reachable history. A published prerelease baseline stops the proposal pending a new decision. A missing or moved baseline tag, shallow history or API error stops the run.

Gemini classifies release impact under [SemVer 2.0.0](https://semver.org/), not commit prefixes. You can set the proposal-only override to `major`, `minor`, `patch` or `none`. `none` creates no artifact unless you also request promotion. An uncertain classification stops the run for review. The first release is `0.1.0`. A major impact below `1.0.0` raises the minor version. Use `promote_to_stable` in the proposal run to choose `1.0.0` from a published `0.y.z` release. Later bumps use standard major, minor and patch arithmetic. Tags use stable numeric versions and retain a published baseline's `v` prefix, if present.

The `evidence` input selects what Gemini reads: `commits-and-diffs` (default) sends commit messages and each commit's text diffs against every parent, including root. `commits` sends the messages only. Binary files add one marker line and no patch data. Merge patches can repeat changes, and reverted changes remain in the history. Non-UTF-8 bytes use escaped text. Large inputs are split without truncation. Gemini summarizes each part and combines summaries until they fit the final request. Coverage checks track every fragment, not model accuracy. Failed, blocked, incomplete or non-shrinking output stops the proposal.

Approval checks the source run, artifact ID and digest, version, target, baseline and tag before writing. Approval ignores proposal-only inputs and uses the saved values. It never moves a tag or edits a published release. A matching existing tag supports retry after draft failure. Tag creation and draft saving are separate writes: if saving fails, the tag stays in place. External tag moves or publication can race these checks. The API has no atomic draft-only update. Review the draft against the comparison before publication.

Requests send repository history to Google and can incur API costs. The job has a 60-minute timeout. `INPUT_BYTES`, `PIECE_CHARS` and the model input are calibration controls, not instruction budgets. No live API run is part of the offline check.

## Check

```cmd
python github\workflows\check_gemini_release.py
```

The check uses temporary Git history and mocked API responses. It does not need API keys or create releases.
