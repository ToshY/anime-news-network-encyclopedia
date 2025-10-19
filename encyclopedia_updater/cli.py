import json
import os
import re
import subprocess as sp
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import click
import requests
from loguru import logger

BASE_DIR = Path(__file__).parent.parent


def _skip_broken_entries_for_category(category: str):
    """
    Returns a list of "broken" entries to skip that contain XML syntax errors in the API.
    """

    skip_entries = []
    match category.lower():
        case "manga":
            skip_entries = [
                5445,  # illegal character code U+001A\n
            ]
        case "_":
            skip_entries = []

    return skip_entries


def _skip_related_entries_for_category(category: str):
    """
    Returns a list of "related" entries to skip that are not available in the API.
    """

    category_lower = category.lower()
    blacklist_path = (
        BASE_DIR / "encyclopedia_updater" / category_lower / "blacklist.json"
    )
    if blacklist_path.exists():
        try:
            with open(blacklist_path, "r", encoding="utf-8") as f:
                skip_entries = json.load(f)
                return skip_entries
        except json.JSONDecodeError:
            print(
                f"Error: Could not decode JSON from {blacklist_path}. Returning empty list."
            )
            return []
        except Exception as e:
            print(
                f"An unexpected error occurred while reading {blacklist_path}: {e}. Returning empty list."
            )
            return []
    else:
        return []


def _xml_datetime_string_to_iso(input_datetime: str) -> str | None:
    try:
        datetime_object = datetime.strptime(input_datetime, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return datetime_object.strftime("%Y-%m-%dT%H:%M:%SZ")


def _datetime_object_to_iso(datetime_object) -> str | None:
    try:
        datetime_object_utc = datetime_object.astimezone(timezone.utc)
    except ValueError:
        return None

    return datetime_object_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_string_to_timestamp(input_datetime: str) -> int:
    iso_string = input_datetime.replace("Z", "+00:00")

    iso_datetime = datetime.fromisoformat(iso_string)

    return int(iso_datetime.timestamp())


def _has_json_contents_diff(file1: Path, file2_dict):
    with tempfile.NamedTemporaryFile(
        mode="w+", suffix=".json", delete=False
    ) as temp_file:
        json.dump(file2_dict, temp_file, sort_keys=False, indent=4, ensure_ascii=False)
        temp_file_path = temp_file.name

    try:
        result = sp.run(
            [
                "bash",
                "-c",
                f'diff <(jq \'del(."+@generated-on", ."+@date-last-modified-at", ."+@date-last-updated-at")\' --sort-keys {str(file1)}) <(jq \'del(."+@generated-on", ."+@date-last-modified-at", ."+@date-last-updated-at")\' --sort-keys {temp_file_path})',
            ],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            text=True,
            shell=False,
        )

        if result.returncode == 0:
            return False
        elif result.returncode == 1:
            return True
        else:
            logger.critical(
                f"An error occurred while comparing JSON files: {result.stdout}"
            )
    finally:
        os.remove(temp_file_path)


def _get_encyclopedia_directory(encyclopedia_directory: Path, category: str) -> Path:
    p = encyclopedia_directory.joinpath(category)
    if not p.is_dir():
        p.mkdir(parents=True, exist_ok=True)

    return p


def _read_report_for_category_file(category: str):
    json_file_path = Path(f"./reports/{category}/report.json")
    if not json_file_path.exists():
        raise FileNotFoundError(f"File {json_file_path} not found.")

    with open(str(json_file_path), "r") as f:
        data = json.load(f)

    return data


def _read_encyclopedia_entry_file(file_path: Path):
    with open(str(file_path), "r") as f:
        data = json.load(f)

    return data


def _get_entries_to_update(
    report: list, category, category_path: Path, threshold_days: int = 30
):
    git_last_modified_timestamp_command = ["git", "log", "-1", "--pretty=format:%ct"]

    result: dict[str, list] = {
        "exist": [],
        "missing": [],
        "outdated": [],
        "skipped": [],
        "broken": [],
    }
    for item in report:
        file_path = category_path / f"{item['id']}.json"

        # Skip items that have invalid XML syntax
        if int(item["id"]) in _skip_broken_entries_for_category(category):
            logger.info(f"Skipping broken item `{item['name']}` ({item['id']}).")
            result["broken"].append({"file": None, "item": item})
            continue

        # Skip items that cannot be retrieved through the API
        if item["name"] is not None:
            keywords = _skip_related_entries_for_category(category)
            if keywords:
                keyword_pattern = "|".join([f"({keyword})" for keyword in keywords])
                full_pattern = rf".*?\((?P<type>{keyword_pattern}).*?\)\s*$"
                match = re.search(
                    full_pattern,
                    item["name"],
                    re.IGNORECASE,
                )

                if match:
                    logger.info(
                        f"Skipping `{match.group('type')}` item `{item['name']}` ({item['id']})."
                    )
                    result["skipped"].append({"file": None, "item": item})
                    continue

        if not file_path.is_file():
            logger.info(f"File does not exist: {file_path}")
            result["missing"].append({"file": None, "item": item})
            continue

        encyclopedia_entry = _read_encyclopedia_entry_file(file_path)
        if "+@date-last-updated-at" in encyclopedia_entry:
            last_updated_at = _iso_string_to_timestamp(
                encyclopedia_entry["+@date-last-updated-at"]
            )
        else:
            # This should only occur when files were added manually and do not include "+@date-last-updated-at" key
            git_last_modified_timestamp_command = (
                git_last_modified_timestamp_command + [str(file_path)]
            )

            response = sp.run(
                git_last_modified_timestamp_command,
                text=True,
                capture_output=True,
            )
            if response.returncode != 0:
                logger.critical(response)
                raise Exception(
                    f"An error occurred ({response.returncode}) while retrieving git last modified timestamp for `{file_path}`: {response.stderr}."
                )

            # If the file hasn't been added to git yet, it produces no timestamp
            if response.stdout:
                last_updated_at = int(response.stdout)
            else:
                last_updated_at = int(_get_current_datetime().timestamp())

        timestamp_difference = int(_get_current_datetime().timestamp()) - int(
            last_updated_at
        )
        timestamp_difference_in_days = timestamp_difference / (60 * 60 * 24)
        if timestamp_difference_in_days > threshold_days:
            logger.info(f"File exists (outdated): {file_path}")
            result["outdated"].append({"file": file_path, "item": item})
            continue

        logger.info(f"File exists (fresh): {file_path}")
        result["exist"].append({"file": file_path, "item": item})

    return result


def _get_current_datetime():
    return datetime.now()


def _get_encyclopedia_entries(url: str, category: str, max_retries: int = 3):
    retries = 0
    while retries < max_retries:
        try:
            encyclopedia_response = requests.get(url, timeout=60)
            encyclopedia_response.raise_for_status()
            break
        except requests.exceptions.Timeout:
            retries += 1
            logger.warning(
                f"Timeout occurred while retrieving the report for URL `{url}` of category `{category}`. Retrying ({retries}/{max_retries})..."
            )
            if retries == max_retries:
                logger.critical(
                    f"Max retries for timout reached. Failed to retrieve the report for URL `{url}` of category `{category}`."
                )
                raise
        except requests.exceptions.HTTPError as err:
            logger.critical(
                f"An error occurred while retrieving the report for URL `{url}` of category `{category}`: {err}"
            )
            raise

    response = sp.run(
        ["yq", "-p=xml", "-o=json"],
        input=encyclopedia_response.text,
        text=True,
        capture_output=True,
    )
    if response.returncode != 0:
        logger.critical(response)
        raise Exception(
            f"An error occurred ({response.returncode}) while converting XML to JSON for the encyclopedia entries from URL `{url}`: {response.stderr}."
        )

    json_data = json.loads(response.stdout)

    return json_data["ann"]


def _apply_additional_date_info(encyclopedia_entry, report_entry):
    # "+@date-added" is the date the file was added to the encyclopedia.
    if "+@date-added" not in encyclopedia_entry:
        # This was already reformatted to ISO in report, so no additional formatting needed here.
        encyclopedia_entry["+@date-added"] = report_entry["item"]["date_added"]

    # "+@date-last-modified-at" denotes when the file was modified through diff check of the JSON files
    if report_entry["file"] is not None and _has_json_contents_diff(
        report_entry["file"], encyclopedia_entry
    ):
        logger.info(f"File contents changed for {encyclopedia_entry['+@id']}")
        encyclopedia_entry["+@date-last-modified-at"] = _datetime_object_to_iso(
            _get_current_datetime()
        )

    # "+@date-last-updated-at" denotes when the file was last updated, modified or not.
    encyclopedia_entry["+@date-last-updated-at"] = _datetime_object_to_iso(
        _get_current_datetime()
    )


def _save_json(
    data, encyclopedia_category_directory: Path, category: str, id_value: int
):
    encyclopedia_path = encyclopedia_category_directory.joinpath(f"{id_value}.json")
    with open(encyclopedia_path, "w", encoding="utf8") as output_file:
        json.dump(data, output_file, sort_keys=False, indent=4, ensure_ascii=False)

    logger.success(
        f"Encyclopedia entry `{id_value}` for category `{category}` saved to `{str(encyclopedia_path)}`."
    )


@logger.catch(reraise=True)
@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog="Repository: https://github.com/ToshY/anime-news-network-encyclopedia",
)
@click.option(
    "--input-directory",
    "-i",
    type=click.Path(exists=False, dir_okay=True, resolve_path=True),
    required=False,
    multiple=False,
    show_default=True,
    default="./encyclopedia",
    help="Path to input encyclopedia directory",
)
@click.option(
    "--output-directory",
    "-o",
    type=click.Path(exists=False, dir_okay=True, resolve_path=True),
    required=False,
    multiple=False,
    show_default=True,
    default="./encyclopedia",
    help="Path to output encyclopedia directory",
)
@click.option(
    "--category",
    "-c",
    type=click.Choice(["anime", "manga"], case_sensitive=False),
    required=False,
    multiple=False,
    help="Retrieve encyclopedia entries for specified category.",
)
@click.option(
    "--entry-type",
    "-t",
    type=click.Choice(["missing", "outdated"], case_sensitive=False),
    required=False,
    multiple=False,
    default="missing",
    show_default=True,
    help="Update 'missing' or 'outdated' encyclopedia entries.",
)
@click.option(
    "--batch-size",
    "-b",
    type=click.IntRange(0, 50),
    required=True,
    multiple=False,
    default=50,
    show_default=True,
    help="Batch amount of entries to update.",
)
@click.option(
    "--days",
    "-d",
    type=int,
    required=True,
    multiple=False,
    default=30,
    show_default=True,
    help="Amount of days when to consider encyclopedia entry outdated since last modified.",
)
def cli(input_directory, output_directory, category, entry_type, batch_size, days):
    input_directory = Path(click.format_filename(input_directory))
    output_directory = Path(click.format_filename(output_directory))

    encyclopedia_category_input_directory = _get_encyclopedia_directory(
        input_directory, category
    )
    encyclopedia_category_output_directory = _get_encyclopedia_directory(
        output_directory, category
    )

    report = _read_report_for_category_file(category)
    entries = _get_entries_to_update(
        report, category, encyclopedia_category_input_directory, days
    )

    to_be_updated_entries = entries[entry_type][:batch_size]
    to_be_updated_entry_ids = [
        str(entry["item"]["id"]) for entry in to_be_updated_entries
    ]
    if not to_be_updated_entry_ids:
        logger.success(f"No `{entry_type}` entries to update.")
        exit(0)

    entry_ids_as_query_param = "/".join(to_be_updated_entry_ids)

    encyclopedia_entry_url = f"https://www.animenewsnetwork.com/encyclopedia/api.xml?title={entry_ids_as_query_param}"
    encyclopedia_entries = _get_encyclopedia_entries(encyclopedia_entry_url, category)

    for key, category_encyclopedia_entries in encyclopedia_entries.items():
        # If only 1 entry is retrieved it will be a dictionary and needs to be in a list
        if isinstance(category_encyclopedia_entries, dict):
            category_encyclopedia_entries = [category_encyclopedia_entries]

        if key == "warning":
            # If only 1 warning entry is found it will be a string and needs to be in a list
            if isinstance(category_encyclopedia_entries, str):
                category_encyclopedia_entries = [category_encyclopedia_entries]

            for warning_not_found_item in category_encyclopedia_entries:
                logger.warning(f"Skipped. Warning: {warning_not_found_item}")
            continue

        if key != category:
            for warning_unexpected_category_item in category_encyclopedia_entries:
                logger.warning(
                    f"Skipped. Unexpected entry type `{key}` for entry `{warning_unexpected_category_item}`."
                )
            continue

        for encyclopedia_entry in category_encyclopedia_entries:
            encyclopedia_id = encyclopedia_entry["+@id"]

            # Get original report item
            matching_report_item = next(
                (
                    entry
                    for entry in to_be_updated_entries
                    if int(entry["item"]["id"]) == int(encyclopedia_id)
                ),
                None,
            )

            # Additional custom date fields
            _apply_additional_date_info(encyclopedia_entry, matching_report_item)

            _save_json(
                encyclopedia_entry,
                encyclopedia_category_output_directory,
                category,
                encyclopedia_id,
            )
