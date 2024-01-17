#
# MIT License
#
# Copyright (c) 2023 Tin Yiu Lai (@soraxas)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

__version__ = "1.0.1"

import sys
import re
import enum
import logging
import subprocess
from typing import Tuple, Optional

from pip._internal.metadata import get_environment
from pip._internal.metadata.pkg_resources import BaseDistribution
from pip._internal.models.direct_url import VcsInfo
from pip._vendor.packaging.version import Version


LOGGER = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter("[%(levelname)s] %(asctime)s @ %(name)s - %(message)s")
)
LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)


class PipAutoInstallError(Exception):
    pass


def set_debug():
    LOGGER.setLevel(logging.DEBUG)


class PipPackageStatus(enum.Enum):
    UpToDate = enum.auto()
    OutDated = enum.auto()
    NotVcsPackage = enum.auto()
    NotGitPackage = enum.auto()
    Found = enum.auto()
    NotFound = enum.auto()
    Failed = enum.auto()


def _get_package(package_name: str) -> Optional[BaseDistribution]:
    for pkg in get_environment(None).iter_installed_distributions(
        # local_only=True,  # only auto-install to local location
        include_editables=False,  # editable package do not need to auto-update
        # user_only=True,
    ):
        if pkg.canonical_name == package_name:
            return pkg

    LOGGER.debug("No existing package found")
    return None


def get_git_package_hash(
    package: BaseDistribution,
) -> Tuple[PipPackageStatus, Optional[str]]:
    LOGGER.debug("Found package '%s' with direct_url %s", package, package.direct_url)

    if package.direct_url is None or not isinstance(package.direct_url.info, VcsInfo):
        LOGGER.debug("Package '%s' is not a vcs package", package.canonical_name)
        return PipPackageStatus.NotVcsPackage, None

    if package.direct_url.info.vcs != "git":
        LOGGER.debug("Package '%s' is not a git package", package.canonical_name)
        return PipPackageStatus.NotGitPackage, None

    LOGGER.debug(
        "Requirement string: %s+%s@%s",
        package.direct_url.info.vcs,
        package.direct_url.url,
        package.direct_url.info.commit_id,
    )
    return PipPackageStatus.Found, package.direct_url.info.commit_id


def _version_not_satisfy(current_version, target_version, operator):
    if operator not in ("==", ">=", "<=", ">", "<"):
        raise ValueError(f"Unknown operator '{operator}'")
    return any(
        (
            (operator == "==" and not (current_version == target_version)),
            (operator == ">=" and not (current_version >= target_version)),
            (operator == "<=" and not (current_version <= target_version)),
            (operator == ">" and not (current_version > target_version)),
            (operator == "<" and not (current_version < target_version)),
        )
    )


def require_package(
    package_name: str,
    pin_version: str = None,
    only_update_existing: bool = False,
    warn_instead_of_error: bool = True,
) -> PipPackageStatus:
    package = _get_package(package_name)

    install_str = package_name

    operator = "=="
    if pin_version is not None:
        result_groups = re.search(r"([<>=]*)([0-9.]*)", pin_version).groups()
        if result_groups[0]:
            operator = result_groups[0]

        if not result_groups[1]:
            raise ValueError(f"'{pin_version}' is not a valid version string")
        pin_version = result_groups[1]
        install_str = f"{install_str}{operator}{pin_version}"

    if package is not None:
        # has existing package
        if pin_version is None:
            # we are done
            LOGGER.debug("Package already installed")
            return PipPackageStatus.UpToDate

        if not _version_not_satisfy(package.version, Version(pin_version), operator):
            LOGGER.debug("Package up-to-date")
            return PipPackageStatus.UpToDate

    elif only_update_existing:
        # no existing package
        LOGGER.debug("Package not found. Skipping.")
        return PipPackageStatus.NotFound

    LOGGER.info("Installing package %s", package_name)

    return __install(install_str, package_name, warn_instead_of_error)


def require_gitpackage(
    package_name: str,
    repo_name: str,
    pin_commit_id: str = None,
    only_update_existing: bool = False,
    warn_instead_of_error: bool = True,
    repo_hostname: str = "github.com",
) -> PipPackageStatus:
    LOGGER.debug("Processing package '%s'", package_name)

    package = _get_package(package_name)

    if package is None:
        LOGGER.info("No existing package found")
        if only_update_existing:
            return PipPackageStatus.NotFound

    else:
        if pin_commit_id is None:
            # satisified
            LOGGER.debug("Package already installed")
            return PipPackageStatus.Found
        else:
            status, result = get_git_package_hash(package)

            if result == pin_commit_id:
                LOGGER.debug("Package up-to-date")
                return PipPackageStatus.UpToDate

            if status in (
                PipPackageStatus.NotVcsPackage,
                PipPackageStatus.NotGitPackage,
            ):
                message = f"Given package {package_name} is not a VCS package."
                if not warn_instead_of_error:
                    raise PipAutoInstallError(message)
                LOGGER.warn(f"{message} Skipping.")
                return PipPackageStatus.NotVcsPackage

            else:
                assert status == PipPackageStatus.Found, f"Unknown status {status}"

    LOGGER.info("Installing package '%s'", package_name)

    repo_hostname = repo_hostname.rstrip("/")
    if not repo_hostname.startswith("http://") and not repo_hostname.startswith(
        "https://"
    ):
        repo_hostname = f"https://{repo_hostname}"
    return __install(
        f"git+{repo_hostname}/{repo_name}", package_name, warn_instead_of_error
    )


def __install(remote_string: str, package_name: str, warn_instead_of_error: bool):
    try:
        output = subprocess.check_output(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                remote_string,
            ]
        )
        LOGGER.debug(output)
    except subprocess.CalledProcessError as e:
        message = f"Unable to auto install {package_name}"
        if not warn_instead_of_error:
            raise PipAutoInstallError(message) from e
        LOGGER.error(message)
        return PipPackageStatus.Failed

    return PipPackageStatus.UpToDate


__all__ = ["require_package", "require_gitpackage"]
