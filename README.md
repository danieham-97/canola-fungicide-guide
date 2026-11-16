# Canola Fungicide Guide

An independent, CPN-style guide to U.S. federal canola/rapeseed foliar white-mold label information. It is not an official Crop Protection Network publication. Efficacy ratings remain blank.

The reviewed baseline contains 122 profiles, 196 federal records, 10 research evidence entries, and a directory covering 50 states, DC and five territories. Its substantive label audit is dated November 13, 2026. Later automated source-check dates are separate from label-review dates.

## Publish on GitHub Pages

1. In this repository, open **Settings → Pages → Build and deployment → Source**, then choose **GitHub Actions**.
2. Under **Actions → Check sources and publish guide**, choose **Run workflow** if the upload did not already start it.
3. Wait for both jobs to succeed, then share the website URL shown by the deployment.

The source repository is [danieham-97/canola-fungicide-guide](https://github.com/danieham-97/canola-fungicide-guide). The default branch is `main`. Source-code changes to that branch trigger a rebuild; reviewed label data is kept separate from automated check results.

GitHub Pages must be enabled by a repository administrator. Organization policy can restrict Pages, Actions or workflow write permissions. No personal access token is embedded in this project. The workflow uses GitHub's temporary repository token.

## Automatic updates: exactly what happens

Every opening loads the latest published shared JSON with a cache-busting query. The browser also attempts fresh direct checks. A scheduled GitHub Actions run checks public sources twice daily at 05:23 and 17:23 UTC, then builds and publishes a new snapshot. There is also a manual trigger and a trigger for source-code pushes to `main`.

The cloud checker compares all tracked federal records, primary profile PDF fingerprints and two Extension feeds. It refreshes metadata and identifies changed documents. Changed registration, ingredient or label evidence withholds the affected application summaries in the UI and exports. A failed check never counts as a match; previously detected changes persist across later network failures. The baseline's rates, PHI, REI, crop/disease interpretation and efficacy fields are never automatically rewritten.

Scheduled checks are not a guarantee that every source is current at the instant of opening. GitHub jobs can be delayed, fail, or be disabled under repository policies. Shared results older than 30 hours are marked stale. The Actions tab contains run logs. GitHub can disable scheduled workflows in inactive public repositories; verify the schedule if updates stop.

The checker does not discover every new registration, approve all-state uses, or crawl all research. Those gaps remain visible in the guide. A qualified reviewer must update `data/reviewed.json` after inspecting changed labels and confirming exact crop, disease, formulation, rate and restrictions. Final marketed labels can differ from EPA master labels.

## Files

- `data/reviewed.json`: reviewed, source-linked baseline.
- `data/source-status.json`: dated machine checks, metadata, review flags and previous holds.
- `src/`: editable CPN-style page, styles and browser logic.
- `scripts/refresh_sources.py`: bounded public-source checker, standard-library Python.
- `scripts/build.py`: self-contained `public/index.html` plus shared source JSON.
- `scripts/persist_status.py`: writes only the generated status file back to the current repository so holds survive subsequent failures.
- `.github/workflows/pages.yml`: check, test, retain history and deploy.
- `.github/workflows/test.yml`: read-only pull-request checks, without publishing.
- `tests/`: mocked change/failure cases and browser-logic checks.

## Local development

Python 3.12+ and Node.js 24 are used in the workflow; no third-party packages are required.

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/refresh_sources.py
python scripts/build.py
node tests/test_app.cjs
```

The public HTML can also be opened as a downloaded file. Its shared relative JSON may be unavailable from a local file; direct source checks will still be attempted. Browser CORS restrictions can block public-source reads. GitHub's cloud checks provide an independent, dated source snapshot.

## Evidence and attribution

All product directions link to the relevant label documents and page numbers. Research sources, scope limitations and review decisions are bundled in the audit export. External source documents are linked rather than copied into the repository. No endorsement by CPN, EPA, Extension institutions or manufacturers is implied. No redistribution license has been selected for the project's original code; external source materials retain their respective rights.

## GitHub references

- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Configure the publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- [Scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
