from setuptools import setup, find_packages  # type: ignore
import os

VERSION = "0.0.1"


def parse_requirements(filename):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), filename),
        encoding="utf-8",
        mode="r",
    ) as file:
        return [
            line.strip() for line in file if line.strip() and not line.startswith("#")
        ]


def parse_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
        mode="r",
    ) as fp:
        return fp.read()


setup(
    name="anime-news-network-encyclopedia",
    description="A command-line utility for retrieving Anime News Network reports and encyclopedia entries.",
    long_description=parse_long_description(),
    long_description_content_type="text/markdown",
    author="ToshY (https://github.com/ToshY)",
    url="https://github.com/ToshY/anime-news-network-encyclopedia",
    project_urls={
        "Issues": "https://github.com/ToshY/anime-news-network-encyclopedia/issues",
        "CI": "https://github.com/ToshY/anime-news-network-encyclopedia/actions",
        "Releases": "https://github.com/ToshY/anime-news-network-encyclopedia/releases",
    },
    license="MIT",
    version=VERSION,
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "report_updater=report_updater.cli:cli",
            "encyclopedia_updater=encyclopedia_updater.cli:cli",
        ],
    },
    install_requires=parse_requirements("requirements.txt"),
    extras_require={
        "dev": parse_requirements("requirements.dev.txt"),
    },
    python_requires=">=3.11",
)
