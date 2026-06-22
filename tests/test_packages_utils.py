"""Tests for tau/packages/utils.py — package source parsing."""
from __future__ import annotations

import sys

import pytest

from tau.packages.types import SourceType
from tau.packages.utils import add_site_packages_path, parse_source


def test_add_site_packages_path_appends_without_shadowing(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    runtime_path = "/runtime/site-packages"
    extension_path = tmp_path / "site-packages"
    monkeypatch.setattr(sys, "path", [runtime_path])

    add_site_packages_path(extension_path)
    add_site_packages_path(extension_path)

    assert sys.path == [runtime_path, str(extension_path)]


def test_add_site_packages_path_ignores_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", ["/runtime/site-packages"])

    add_site_packages_path(None)

    assert sys.path == ["/runtime/site-packages"]


class TestParseSource:
    # ── PyPI ────────────────────────────────────────────────────────────────────

    def test_pypi_prefix_bare(self):
        r = parse_source("pypi:requests")
        assert r.source == SourceType.PYPI
        assert r.name == "requests"
        assert r.version is None
        assert r.install_spec == "requests"

    def test_pypi_prefix_with_version(self):
        r = parse_source("pypi:requests@2.31.0")
        assert r.source == SourceType.PYPI
        assert r.name == "requests"
        assert r.version == "2.31.0"
        assert r.install_spec == "requests==2.31.0"

    def test_bare_name_treated_as_pypi(self):
        r = parse_source("requests")
        assert r.source == SourceType.PYPI
        assert r.name == "requests"

    def test_bare_name_with_version(self):
        r = parse_source("requests@2.0.0")
        assert r.source == SourceType.PYPI
        assert r.version == "2.0.0"
        assert r.install_spec == "requests==2.0.0"

    # ── Git ─────────────────────────────────────────────────────────────────────

    def test_git_prefix(self):
        r = parse_source("git+https://github.com/user/myrepo")
        assert r.source == SourceType.GIT
        assert r.name == "myrepo"

    def test_git_with_tag(self):
        r = parse_source("git+https://github.com/user/myrepo@v1.0.0")
        assert r.source == SourceType.GIT
        assert r.name == "myrepo"
        assert r.install_spec == "git+https://github.com/user/myrepo@v1.0.0"

    def test_git_strips_dot_git(self):
        r = parse_source("git+https://github.com/user/myrepo.git")
        assert r.name == "myrepo"

    # ── Local ────────────────────────────────────────────────────────────────────

    def test_absolute_path(self, tmp_path):
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        r = parse_source(str(pkg_dir))
        assert r.source == SourceType.LOCAL
        assert r.name == "mypkg"

    def test_relative_path(self):
        r = parse_source("./my-package")
        assert r.source == SourceType.LOCAL
        assert r.name == "my-package"

    def test_tilde_path(self):
        r = parse_source("~/projects/mypkg")
        assert r.source == SourceType.LOCAL
        assert r.name == "mypkg"

    # ── Raw field preserved ──────────────────────────────────────────────────────

    def test_raw_field_preserved(self):
        source_str = "pypi:requests@1.0.0"
        r = parse_source(source_str)
        assert r.raw == source_str

    # ── Whitespace trimmed ───────────────────────────────────────────────────────

    def test_whitespace_stripped(self):
        r = parse_source("  requests  ")
        assert r.name == "requests"

    # ── Invalid ──────────────────────────────────────────────────────────────────

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError):
            parse_source("!@#$%^")
