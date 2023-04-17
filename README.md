# Usage:

```py
import pip_ensure_version

# pip_ensure_version.set_debug()

pip_ensure_version.require_package(
    "tqdm",     # package name
    "4.47",     # pin version (optional)
)

pip_ensure_version.require_gitpackage(
    "soraxas-toolbox",                          # package name
    "soraxas/python-soraxas_toolbox",           # repo name (default to github)
    "aa00d757b58c43523d7c518cdac600d4a75c6015", # commit id (optional)
)

# at this point, the requested package will be up-to-date
import tqdm
import soraxas_toolbox

...

```
