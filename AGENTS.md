# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this repo is

An auto-updated **data repository** that mirrors [Anime News Network](https://www.animenewsnetwork.com) (ANN) reports and encyclopedia entries as JSON. Nearly all files (~37k) are generated data committed by scheduled GitHub Actions; the actual code is two small Python CLIs plus a Taskfile.

```
report_updater/          # CLI: fetches ANN reports (XML) -> reports/<category>/report.json
encyclopedia_updater/    # CLI: fetches ANN encyclopedia entries -> encyclopedia/<category>/<id>.json
  anime|manga/blacklist.json   # "related" name suffixes the API can't serve (skipped)
  anime|manga/whitelist.json   # suffixes that look related but ARE served by the API
reports/<category>/report.json # anime, manga, person, company  (generated)
encyclopedia/<category>/<id>.json  # anime, manga only           (generated)
Taskfile.yml             # all local commands (Docker-based)
.github/workflows/       # scheduled data jobs + lint/type/security checks
```

## Generated data: do not hand-edit

- `reports/**` and `encyclopedia/**` are written by the CLIs/workflows. Don't edit, reformat, or mass-rewrite them manually; change the code that produces them instead.
- `blacklist.json` / `whitelist.json` are regenerated weekly by `task blacklist:generate` (the `blacklist.yml` workflow). Hand edits get overwritten.
- These directories are huge. Avoid globbing/reading them wholesale — inspect single files (e.g. `encyclopedia/anime/1.json`) or use `jq` on one report.
- Most commits on `main` are bot commits ("Update encyclopedia entries", "Update reports"); expect `main` to move frequently.

## Data pipeline

1. **Reports** (`report_updater/cli.py`, daily `0 0 * * *`): fetches `reports.xml?id=148|149|150|151` (anime/manga/person/company), parses with `xml.etree`, converts `date_added` to ISO 8601 (`%Y-%m-%dT%H:%M:%SZ`). Anime/manga are merged with the search report (`id=155`) for `gid`, `entry_type`, `precision`, `vintage`. Person is fetched in batches of 50k via `nskip` (`nlist=all` returns 500).
2. **Encyclopedia** (`encyclopedia_updater/cli.py`, every 4h `15 */4 * * *`): reads the local `report.json`, classifies each id as `missing` / `outdated` (older than `--days`, default 30) / `exist` / `skipped` (name suffix matches blacklist) / `broken` (hardcoded ids with invalid XML, e.g. manga `5445`). Fetches up to 50 ids per run from `api.xml?title=<id>/<id>/...`, converts XML→JSON with **`yq -p=xml -o=json`**, then saves.
3. **Release** (daily `30 0 * * *`): tags `YYYY.MM.DD-<run_id>`.

Encyclopedia JSON conventions (from yq): attributes are `+@name`, text content is `+content`. Custom fields added by the updater:
- `+@date-added` — copied from the report's `date_added` (set once).
- `+@date-last-modified-at` — set only when content changed (diffed with `jq --sort-keys`, ignoring `+@generated-on` and the custom date fields).
- `+@date-last-updated-at` — set on every update; drives the "outdated" check.

JSON is written with `indent=4`, `ensure_ascii=False`, `sort_keys=False` — keep this so diffs stay minimal.

The yq XML quirks matter: a single child comes back as a dict/string instead of a list (the CLI normalizes `warning` and category keys for this).

## External tools & API etiquette

- Runtime needs `yq` (mikefarah, v4) and `jq` on `PATH`, plus `git` (used for last-modified fallback) and `bash` (used for the diff check). The Docker image installs all of them.
- ANN API: keep batches ≤ 50 ids (enforced by `--batch-size` `IntRange(0, 50)`) and keep the `time.sleep(1)` between requests. Don't add parallel/bulk fetching.
- ANN TOS requires crediting ANN and linking to the encyclopedia entry; keep the README disclaimer intact.

## Commands

Everything runs through Docker Compose via [Task](https://taskfile.dev). Python is 3.11.

```bash
task run:report -- -c anime                 # update one report (omit -c for all)
task run:encyclopedia -- -c anime -t missing  # one batch; -t missing|outdated, -b batch size, -d days
task run:encyclopedia:all c=manga t=missing   # loop batches until done

task ruff        # / task ruff:fix
task black       # / task black:fix
task mypy

task actionlint   # lint workflows
task zizmor       # security-audit workflows + dependabot.yml (config: zizmor.yml)
task pinact       # check actions are SHA-pinned / task pinact:fix to pin them

task blacklist:generate c=anime           # regenerate black/whitelist from API probes
task blacklist:cleanup dry=true           # list encyclopedia files that are blacklisted (dry=false deletes)
```

Without Docker: `pip install -r requirements.txt -r requirements.dev.txt`, then `python -m report_updater ...` / `python -m encyclopedia_updater ...` from the repo root (paths like `./reports/<category>/report.json` are resolved relative to CWD).

CI writes to `/tmp/...` via `-o` and commits via artifacts; locally the default output is the in-repo `./reports` / `./encyclopedia`, so running the CLIs locally **modifies tracked data files**. Use `-o <scratch dir>` when you only want to test.

## Code quality

CI (`codequality.yml`, `codestyle.yml`, `statictyping.yml`) runs on push/PR to `main`:

- `ruff check .` (ruff 0.6)
- `black . --check` (black 24.8)
- `mypy .` (mypy 1.11)

Run all three before finishing a code change (also wired as local pre-commit hooks). There are no config files for these tools, so defaults apply. There is no test suite; verify changes by running the CLI against a scratch output dir with `LOGURU_LEVEL=INFO`.

## GitHub Actions

When changing anything under `.github/`, run `task actionlint`, `task zizmor` and `task pinact`; CI runs actionlint and zizmor too (`actionlint.yml`, `zizmor.yml`), and they are wired as pre-commit hooks.

- Pin every action to a full commit SHA with a version comment (`uses: owner/action@<sha> # vX.Y.Z`); `task pinact:fix` does this. zizmor enforces it (`hash-pin` policy).
- Each workflow sets `permissions: {}` at the top; each job grants only what it needs (`contents: read` to check out, `contents: write` only for jobs that commit, `{}` for jobs without a checkout).
- Checkouts use `persist-credentials: false`, except jobs that push via `git-auto-commit-action`, which set it to `true` explicitly.
- Lint/check workflows trigger on `pull_request`, not `pull_request_target`, so they check the PR's code without a privileged token.
- Don't interpolate `${{ ... }}` from untrusted inputs directly into `run:` scripts; pass them through `env:`.

CI checkouts are sparse (`sparse-checkout` in `actions/checkout`, which implies `--filter=blob:none`) so jobs don't download the ~450 MB of data or the 1+ GiB history. If a job starts needing other paths, add them to that job's `sparse-checkout` list. Don't add `fetch-depth: 0`. Jobs that commit data use a non-cone checkout that excludes `encyclopedia/` and `reports/`, then `git sparse-checkout add` only the files they are about to write.

## Style notes

- CLIs use `click` (options with short flags, `-h/--help`), logging via `loguru` (`LOGURU_LEVEL` env, default `SUCCESS`), HTTP via `requests` with explicit timeouts.
- Private helpers are module-level functions prefixed with `_`; keep the existing single-file-per-CLI structure unless asked otherwise.
- Dependencies are pinned to minor versions (`pkg==X.Y.*`) in `requirements*.txt`; `setup.py` reads from those files.
- `.gitattributes` export-ignores code/config so release archives contain only data — add new top-level code/config files there too.
