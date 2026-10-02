"""Tests for Switchyard CLI commands."""

import pytest
from switchyard.cli import main


def test_cli_workers(capsys):
    exit_code = main(["workers"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "codex" in captured.out
    assert "copilot" in captured.out
    assert "agy" in captured.out
    assert "qwen-local" in captured.out


def test_cli_route(capsys):
    exit_code = main(["route", "-c", "coding", "-c", "debugging", "Inspect function"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "selected: codex" in captured.out
    assert "required capabilities matched: coding, debugging" in captured.out


def test_cli_run(capsys):
    exit_code = main(["run", "-c", "reasoning", "Summarize report"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "selected: qwen-local" in captured.out
    assert "--- Worker Result ---" in captured.out
    assert "Executed by qwen-local: Summarize report" in captured.out


def test_cli_no_match(capsys):
    exit_code = main(["route", "-c", "unsupported-capability", "Task"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No available workers found" in captured.err


def test_cli_workers_from_config(tmp_path, capsys):
    config = tmp_path / "workers.toml"
    config.write_text(
        """
[[workers]]
name = "configured-qwen"
kind = "mock"
capabilities = ["reasoning"]
speed = "medium"
cost = "free"
"""
    )

    exit_code = main(["--config", str(config), "workers"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "configured-qwen" in captured.out
    assert "codex" not in captured.out
