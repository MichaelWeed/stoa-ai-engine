"""Tests for the AST safety validator."""

import pytest
from stoa.compiler.validator import ASTValidator, ValidationError


def test_safe_code_passes():
    code = """
total = sum([1, 2, 3])
result = {"total": total}
"""
    v = ASTValidator()
    assert v.validate(code).passed


def test_eval_is_blocked():
    code = "result = eval('1 + 1')"
    v = ASTValidator()
    result = v.validate(code)
    assert not result.passed
    assert any("eval" in violation for violation in result.violations)


def test_exec_is_blocked():
    code = "exec('import os')"
    v = ASTValidator()
    result = v.validate(code)
    assert not result.passed


def test_subprocess_import_is_blocked():
    code = "import subprocess\nresult = subprocess.run(['ls'])"
    v = ASTValidator()
    result = v.validate(code)
    assert not result.passed


def test_os_import_is_blocked():
    code = "import os\nresult = os.listdir('.')"
    v = ASTValidator()
    result = v.validate(code)
    assert not result.passed


def test_validate_or_raise_on_safe_code():
    code = "result = [x * 2 for x in range(10)]"
    ASTValidator().validate_or_raise(code)  # should not raise


def test_validate_or_raise_on_dangerous_code():
    code = "result = eval('dangerous')"
    with pytest.raises(ValidationError):
        ASTValidator().validate_or_raise(code)


def test_syntax_error_is_caught():
    code = "def broken(:"
    result = ASTValidator().validate(code)
    assert not result.passed
    assert any("Syntax" in v for v in result.violations)
