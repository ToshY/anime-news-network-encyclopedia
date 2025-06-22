<h1 align="center">📚 Anime News Network Encyclopedia </h1>

<div align="center">
    <img src="https://img.shields.io/github/v/release/toshy/anime-news-network-encyclopedia?logo=github&label=Release" alt="GitHub Release">
    <img src="https://img.shields.io/github/actions/workflow/status/toshy/anime-news-network-encyclopedia/codestyle.yml?branch=main&label=Black" alt="Black">
    <img src="https://img.shields.io/github/actions/workflow/status/toshy/anime-news-network-encyclopedia/codequality.yml?branch=main&label=Ruff" alt="Ruff">
    <img src="https://img.shields.io/github/actions/workflow/status/toshy/anime-news-network-encyclopedia/statictyping.yml?branch=main&label=Mypy" alt="Mypy">
    <img src="https://img.shields.io/github/actions/workflow/status/toshy/anime-news-network-encyclopedia/security.yml?branch=main&label=Security%20check" alt="Security check" />
    <br /><br />
    <div>An auto-updated repository for retrieving reports and encyclopedia entries of anime, manga, people and companies from <a href="https://www.animenewsnetwork.com">Anime News Network</a>.</div>
</div>

## 📚 Reports & Encyclopedia

All data retrieved from the Anime News Network API is converted from XML to JSON using [yq](https://github.com/mikefarah/yq).

### Reports

- Reports for the following categories are available: `anime`, `manga`, `person` and `company`.
- Reports for each category can be found inside the [`./reports/<category>`](./reports) directory, denoted as `report.json`.
- Reports are updated daily at cron schedule `0 0 * * *` (actual workflow execution time may be [delayed](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule)).

### Encyclopedia

- Encyclopedia entries for the following categories are available: `anime` and `manga`.
- Encyclopedia entries for each category can be found inside the [`./encyclopedia/<category>`](./encyclopedia) directory, denoted as `<id>.json`, where the `<id>` corresponds to the id of the encyclopedia entry.
- Encyclopedia entries are **not** available for ["related"](https://www.animenewsnetwork.com/encyclopedia/) entries, including but not limited to, `live-action` (type), `cancelled` (status), `Chinese` (non-Japanese).
- Encyclopedia entries are updated (when missing or outdated) in batches of `50` items per workflow run at cron schedule `15 */4 * * *` (actual workflow execution time may be [delayed](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule)).

### ✍️ Notes

- The `date_added` property in the reports is converted to [ISO 8601](https://en.wikipedia.org/wiki/ISO_8601) standard.
- Additional datetime properties are added to the encyclopedia entries:
  - `+@date-added`: denotes the `date_added` from the `report.json`.
  - `+@date-last-modified-at`: denotes when the encyclopedia entry was last modified (with a `git diff` check).
  - `+@date-last-updated-at`: denotes when the encyclopedia entry was last updated (with the encyclopedia updater), even if it was not modified (to track outdated entries).

### 📅 Releases

- [Releases](https://github.com/ToshY/anime-news-network-encyclopedia/releases) are created daily at cron schedule `30 0 * * *` (actual workflow execution time may be [delayed](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule)).

## ℹ️ Disclaimer

* The source for the reports is [Anime News Network](https://www.animenewsnetwork.com).
* This repository is _not_ affiliated with Anime News Network.

### ✍️ Anime News Network TOS

> We provide this API free of charge but you must
> 1. list Anime News Network as the source of the data
> 2. include a link to the relevant Encyclopedia entry (like "full details at Anime News Network") on any page that displays anime/manga/person details

For more information, see [animenewsnetwork.com/encyclopedia/api.php](https://www.animenewsnetwork.com/encyclopedia/api.php).

## ❕ License

This repository comes with a [MIT license](./LICENSE).
