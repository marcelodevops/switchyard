"""Tests for the Eiren Tools adapter boundary (one tool: process_list)."""

import inspect
from unittest.mock import patch

import pytest

from switchyard.eiren_tools import build_server, run_process_list
from switchyard.processes import ProcessInfo

SAMPLE = [
    ProcessInfo(
        pid=37953, ppid=37951, state="R+", cpu_percent=796.0,
        memory_percent=26.9, rss_kib=18067912, elapsed="05:50",
        command="/Users/dev/bin/qwen38 46",
    )
]


def test_no_filter_returns_structured_records():
    with patch("switchyard.eiren_tools.list_processes", return_value=SAMPLE) as ps:
        result = run_process_list()
    ps.assert_called_once_with(None)
    assert result["processes"][0]["pid"] == 37953
    assert result["processes"][0]["command"] == "/Users/dev/bin/qwen38 46"


def test_command_contains_passes_literal_substring_to_capability():
    with patch("switchyard.eiren_tools.list_processes", return_value=[]) as ps:
        run_process_list(command_contains="qwen38")
    ps.assert_called_once_with("qwen38")


def test_empty_match_is_valid_empty_result():
    with patch("switchyard.eiren_tools.list_processes", return_value=[]):
        assert run_process_list(command_contains="nothing") == {"processes": []}


def test_inspection_failure_raises_controlled_error():
    from switchyard.processes import ProcessInspectionError

    def boom(_command_contains=None):
        raise ProcessInspectionError("Unable to read process snapshot: ps died")

    with patch("switchyard.eiren_tools.list_processes", side_effect=boom):
        with pytest.raises(ProcessInspectionError, match="Unable to read process snapshot"):
            run_process_list()


def test_output_preserves_typed_fields():
    with patch("switchyard.eiren_tools.list_processes", return_value=SAMPLE):
        record = run_process_list()["processes"][0]
    assert record == {
        "pid": 37953, "ppid": 37951, "state": "R+", "cpu_percent": 796.0,
        "memory_percent": 26.9, "rss_kib": 18067912, "elapsed": "05:50",
        "command": "/Users/dev/bin/qwen38 46",
    }


def test_input_cannot_specify_commands_or_executables():
    signature = inspect.signature(run_process_list)
    assert list(signature.parameters) == ["command_contains"]
    with pytest.raises(ValueError, match="must be a string"):
        run_process_list(command_contains=["rm", "-rf"])
    with pytest.raises(TypeError):
        run_process_list(command_contains="x", extra_command="whoami")


def test_non_string_command_contains_is_rejected_before_ps():
    with patch("switchyard.eiren_tools.list_processes") as ps:
        with pytest.raises(ValueError):
            run_process_list(command_contains=1234)
    ps.assert_not_called()


@pytest.mark.asyncio
async def test_server_exposes_exactly_one_tool():
    server = build_server()
    tools = await server.list_tools()
    assert [tool.name for tool in tools] == ["process_list"]
    schema = tools[0].input_schema
    assert set(schema["properties"]) == {"command_contains"}
    assert "command" not in schema["properties"]
    annotations = tools[0].annotations
    assert annotations.read_only_hint is True
    assert annotations.open_world_hint is False
