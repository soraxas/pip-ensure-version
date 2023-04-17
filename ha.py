import pip_ensure_version


pip_ensure_version.set_debug()

pip_ensure_version.require_package(
    "tqdm",
    "4.47",
)

pip_ensure_version.require_gitpackage(
    "soraxas-toolbox",
    "soraxas/python-soraxas_toolbox",
    "aa00d757b58c43523d7c518cdac600d4a75c6015",
)
import soraxas_toolbox
