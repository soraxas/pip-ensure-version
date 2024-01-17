import re
from os import path

from setuptools import setup

# read the contents of README file
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

from pip_ensure_version import __version__ as version_str

setup(
    name="pip-ensure-version",
    version=version_str,
    description="Ensure pip package version, and auto update if not",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Tin Lai (@soraxas)",
    author_email="oscar@tinyiu.com",
    license="MIT",
    url="https://github.com/soraxas/pip-ensure-version",
    python_requires=">=3.6",
    install_requires=["pip"],
    packages=[
        "pip_ensure_version",
    ],
)
