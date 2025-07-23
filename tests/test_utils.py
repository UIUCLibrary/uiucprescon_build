import os
import sys
import pytest

from uiucprescon.build import utils


def test_set_env_var():
    """Test the set_env_var context manager."""
    original_env = os.environ.copy()
    test_env = {"TEST_VAR": "test_value"}

    with utils.set_env_var(test_env):
        assert os.environ["TEST_VAR"] == "test_value"
        assert "TEST_VAR" in os.environ

    # Check that the original environment is restored
    assert os.environ == original_env

    # Check that the test variable is no longer present
    assert "TEST_VAR" not in os.environ


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="This test is specific to Windows case insensitivity"
)
def test_set_env_var_keep_in_sensitive_on_window():
    """Test set_env_var keeps environment vars are case-insensitive on Win."""
    original_env = os.environ.copy()
    test_env = {"TEST_VAR": "test_value"}

    with utils.set_env_var(test_env):
        assert os.environ["TEST_VAR"] == "test_value"
        assert "TEST_VAR" in os.environ
        assert "test_var" in os.environ  # Check case insensitivity

    # Check that the original environment is restored
    assert os.environ == original_env

    # Check that the test variable is no longer present
    assert "TEST_VAR" not in os.environ


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="This test is to make sure that env var is still accessible "
           "after using set_env_var"
)
@pytest.mark.parametrize(
    "variable",
    [
        "ProgramFiles", "ProgramFiles(x86)",
        "programfiles", "programfiles(x86)",
        "PROGRAMFILES", "PROGRAMFILES(X86)",
    ]
)
def test_set_env_var_does_not_make_program_files_impossible_to_get(variable):
    test_env = {"TEST_VAR": "test_value"}
    assert variable in os.environ,\
        f"{variable} should already be in the environment"
    with utils.set_env_var(test_env):
        pass
    assert variable in os.environ