import inspect
from pathlib import Path
from typing import Any, Callable

# TODO: rename this file as this not only meant for reductions


def emit_module_imports(check: Callable[..., bool]) -> str:
    this_source_file = inspect.getsourcefile(emit_module_imports)
    assert this_source_file

    check_name = check.__name__
    check_module_path = inspect.getsourcefile(check)
    assert check_module_path
    check_module = inspect.getmodulename(check_module_path)

    prologue = f"""import importlib
import sys
from pathlib import Path
sys.path.insert(0, "{str(Path(check_module_path).parent)}")

from {check_module} import {check_name}
"""
    return prologue


def emit_call(check: Callable[..., bool], kwargs: dict[Any, Any]) -> str:
    if not kwargs:
        call = "exit(not " + check.__name__ + "(code))"
    else:
        call = (
            "exit(not "
            + check.__name__
            + "(code, "
            + ", ".join(f"{k} = {v}" for k, v in kwargs.items())
            + "))"
        )
    return f"""with open(\"code.c\", \"r\") as f:
    code = f.read()
{call}
    """


def make_interestingness_check(
    check: Callable[..., bool],
    add_args: dict[Any, Any],
) -> str:
    """
    Helper function to create a script useful for use with diopter.Reducer

    Args:
        check: a Python function that implements the check, its first argument
        should be the code (str) to test.
        add_args: additional arguments passed to the check, these hardcoded in
        the script

    Returns:
        The script
    """
    prologue = "#!/usr/bin/env python3"
    return "\n".join(
        (
            prologue,
            emit_module_imports(check),
            emit_call(check, add_args),
        )
    )
