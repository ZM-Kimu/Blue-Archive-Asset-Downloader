from __future__ import annotations

import sys
from importlib import util
from pathlib import Path
from typing import Any


def load_generated_module(
    package_dir: Path,
    module_name: str,
    package_prefix: str,
) -> Any:
    package_name = f"{package_prefix}_{abs(hash(str(package_dir)))}"
    if package_name not in sys.modules:
        package_spec = util.spec_from_file_location(
            package_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
        assert package_spec is not None and package_spec.loader is not None
        package = util.module_from_spec(package_spec)
        sys.modules[package_name] = package
        package_spec.loader.exec_module(package)

    spec = util.spec_from_file_location(
        f"{package_name}.{module_name}",
        package_dir / f"{module_name}.py",
    )
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
