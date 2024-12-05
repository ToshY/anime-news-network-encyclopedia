import json
import time
import xml.etree.ElementTree as elementTree
from pathlib import Path
from datetime import datetime

import click
import requests
from loguru import logger


def _get_report_directory(report_directory: Path, category: str) -> Path:
    p = report_directory.joinpath(category)
    if not p.is_dir():
        p.mkdir(parents=True, exist_ok=True)

    return p


def _datetime_to_iso(input_datetime: str) -> str | None:
    try:
        datetime_object = datetime.strptime(input_datetime, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return datetime_object.strftime("%Y-%m-%dT%H:%M:%SZ")


def _save_json(data, report_category_directory: Path, category: str):
    report_path = report_category_directory.joinpath("report.json")
    with open(report_path, "w", encoding="utf8") as output_file:
        json.dump(data, output_file, sort_keys=False, indent=4, ensure_ascii=False)

    logger.info(f"Report for category `{category}` saved to `{str(report_path)}`.")


def _get_common_data(url: str, category: str):
    try:
        report_response = requests.get(url, timeout=60)
        report_response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.critical(
            f"An error occurred while retrieving the report for URL `{url} of category `{category}`: {err}"
        )

        raise

    root_element = elementTree.fromstring(report_response.content)

    return [
        {
            "id": (
                item.find(category).attrib["href"].split("=")[1]  # type: ignore[union-attr]
                if item.find(category)  # type: ignore[union-attr]
                .attrib["href"]
                .split("=")[1]
                else None
            ),
            "name": item.find(category).text,  # type: ignore[union-attr]
            "date_added": _datetime_to_iso(
                item.find("date_added").text  # type: ignore[arg-type,union-attr]
            ),
        }
        for item in root_element.findall(".//item")
    ]


def _get_search_data(url: str):
    try:
        report_response = requests.get(url)
        report_response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.critical(
            f"An error occurred while retrieving the report for search url `{url}`: {err}"
        )

        raise

    root_element = elementTree.fromstring(report_response.content)
    return [
        {
            "id": _get_text(item, "id") if _get_text(item, "id") else None,
            "gid": _get_text(item, "gid") if _get_text(item, "gid") else None,
            "entry_type": _get_text(item, "entry_type"),
            "name": _get_text(item, "name"),
            "precision": _get_text(item, "precision"),
            "vintage": _get_text(item, "vintage"),
        }
        for item in root_element.findall(".//item")
    ]


def _combine_search_data(common_data, search_data):
    # Combine based on ID
    search_report_dict = {item["id"]: item for item in search_data}

    # Merge if a match is found else fill missing fields
    return [
        (
            {**item1, **search_report_dict[item1["id"]]}
            if item1["id"] in search_report_dict
            else {
                **item1,
                "gid": None,
                "entry_type": None,
                "precision": None,
                "vintage": None,
            }
        )
        for item1 in common_data
    ]


def get_anime_report():
    """
    Retrieves an anime report by combining recently added and standard reports for anime.
    """
    category = "anime"
    recently_added_data = _get_common_data(
        "https://www.animenewsnetwork.com/encyclopedia/reports.xml?id=148&nlist=all",
        category,
    )
    search_report_data = _get_search_data(
        "https://www.animenewsnetwork.com/encyclopedia/reports.xml?id=155&nlist=all&type=anime"
    )

    combined_data = _combine_search_data(recently_added_data, search_report_data)

    return combined_data


def get_manga_report():
    """
    Retrieves a manga report by combining recently added and standard reports for manga.
    """
    category = "manga"
    recently_added_data = _get_common_data(
        "https://www.animenewsnetwork.com/encyclopedia/reports.xml?id=149&nlist=all",
        category,
    )
    search_report_data = _get_search_data(
        "https://www.animenewsnetwork.com/encyclopedia/reports.xml?id=155&nlist=all&type=manga"
    )

    combined_data = _combine_search_data(recently_added_data, search_report_data)

    return combined_data


def get_person_report():
    """
    Retrieves a person report.

    The API endpoint is different from the others and requires special handling as the "all" returns 500 error.

    Needs to be batched in order to function. By using nlist=1, the initial most recently added person is retrieved,
    and the id serves as an approximate of the amount of person there are in the database. Then it can be batched
    using `nskip`. Batch will consist of 50k person at a time with sleep of 1 second to prevent rate limiting.
    """
    category = "person"
    batch_size = 50000
    initial_people_data = _get_common_data(
        "https://www.animenewsnetwork.com/encyclopedia/reports.xml?id=150&nlist=1",
        category,
    )

    people_data = []
    approximate_amount_of_people = int(initial_people_data[0]["id"])
    for offset in range(0, approximate_amount_of_people, batch_size):
        time.sleep(1)
        url = f"https://www.animenewsnetwork.com/encyclopedia/reports.xml?id=150&nlist=50000&nskip={offset}"
        people_data = people_data + _get_common_data(url, category)

    return people_data


def get_company_report():
    """
    Retrieves a company report.
    """
    category = "company"
    company_data = _get_common_data(
        "https://www.animenewsnetwork.com/encyclopedia/reports.xml?id=151&nlist=all",
        category,
    )

    return company_data


def _get_text(element, tag, default=None):
    found = element.find(tag)
    return found.text if found is not None else default


@logger.catch(reraise=True)
@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog="Repository: https://github.com/ToshY/anime-news-network-encyclopedia",
)
@click.option(
    "--output-directory",
    "-o",
    type=click.Path(exists=False, dir_okay=True, resolve_path=True),
    required=False,
    multiple=False,
    show_default=True,
    default="./reports",
    help="Path to output reports directory",
)
@click.option(
    "--category",
    "-c",
    type=click.Choice(["anime", "manga", "company", "person"], case_sensitive=False),
    required=False,
    multiple=False,
    show_default=True,
    help="Retrieve report for specified category.",
)
def cli(output_directory, category):
    output_directory = Path(click.format_filename(output_directory))

    if category is None:
        # Sleep to prevent API rate batch_size
        anime_data = get_anime_report()
        report_category_output_directory = _get_report_directory(
            output_directory, "anime"
        )
        _save_json(anime_data, report_category_output_directory, "anime")
        time.sleep(1)

        manga_data = get_manga_report()
        report_category_output_directory = _get_report_directory(
            output_directory, "manga"
        )
        _save_json(manga_data, report_category_output_directory, "manga")
        time.sleep(1)

        company_data = get_company_report()
        report_category_output_directory = _get_report_directory(
            output_directory, "company"
        )
        _save_json(company_data, report_category_output_directory, "company")
        time.sleep(1)

        person_data = get_person_report()
        report_category_output_directory = _get_report_directory(
            output_directory, "person"
        )
        _save_json(person_data, report_category_output_directory, "person")

        exit(0)

    match category.lower():
        case "anime":
            data = get_anime_report()
            report_category_output_directory = _get_report_directory(
                output_directory, category
            )
            _save_json(data, report_category_output_directory, category)
        case "manga":
            data = get_manga_report()
            report_category_output_directory = _get_report_directory(
                output_directory, category
            )
            _save_json(data, report_category_output_directory, category)
        case "person":
            data = get_person_report()
            report_category_output_directory = _get_report_directory(
                output_directory, category
            )
            _save_json(data, report_category_output_directory, category)
        case "company":
            data = get_company_report()
            report_category_output_directory = _get_report_directory(
                output_directory, category
            )
            _save_json(data, report_category_output_directory, category)
        case _:
            raise ValueError(f"Invalid category: {category}")
