from ._version import __version__

import sys
import enum
import logging
import subprocess
from typing import Tuple, Optional

from pip._internal.metadata import get_environment
from pip._internal.metadata.pkg_resources import BaseDistribution
from pip._internal.models.direct_url import VcsInfo
from pip._vendor.packaging.version import Version


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class PipAutoInstallError(Exception):
    pass


def set_debug():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(asctime)s @ %(name)s - %(message)s")
    )

    LOGGER.addHandler(handler)


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

    LOGGER.info("No existing package found")
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


def require_package(
    package_name: str,
    pin_version: str = None,
    only_update_existing: bool = False,
    warn_instead_of_error: bool = True,
) -> PipPackageStatus:
    package = _get_package(package_name)

    install_str = package_name

    if package is not None:
        # has existing package
        if pin_version is None:
            # we are done
            LOGGER.debug("Package already installed")
            return PipPackageStatus.UpToDate

        if Version(pin_version) == package.version:
            LOGGER.debug("Package up-to-date")
            return PipPackageStatus.UpToDate
        install_str = f"{install_str}=={pin_version}"

    elif only_update_existing:
        # no existing package
        LOGGER.debug("Package not found. Skipping.")
        return PipPackageStatus.NotFound

    LOGGER.info("Installing package")

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
        print(output)
    except subprocess.CalledProcessError as e:
        message = f"Unable to auto install {package_name}"
        if not warn_instead_of_error:
            raise PipAutoInstallError(message) from e
        print(message)
        return PipPackageStatus.Failed

    return PipPackageStatus.UpToDate


__all__ = ["require_package", "require_gitpackage"]
