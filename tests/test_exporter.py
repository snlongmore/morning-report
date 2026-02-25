"""Tests for the Word document exporter."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from morning_report.report.exporter import export_docx


class TestExportDocx:
    def test_calls_pandoc_with_correct_args(self, tmp_path):
        md_file = tmp_path / "2026-02-25.md"
        md_file.write_text("# Morning Report")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("morning_report.report.exporter.subprocess.run", return_value=mock_result) as mock_run:
            result = export_docx(md_file)

        expected_output = tmp_path / "2026-02-25.docx"
        mock_run.assert_called_once_with(
            ["pandoc", str(md_file), "-o", str(expected_output), "--from=markdown", "--to=docx"],
            capture_output=True,
            text=True,
        )
        assert result == expected_output

    def test_custom_output_path(self, tmp_path):
        md_file = tmp_path / "report.md"
        md_file.write_text("# Report")
        custom_output = tmp_path / "custom" / "output.docx"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("morning_report.report.exporter.subprocess.run", return_value=mock_result) as mock_run:
            result = export_docx(md_file, output_path=custom_output)

        assert result == custom_output
        args = mock_run.call_args[0][0]
        assert args[3] == str(custom_output)

    def test_raises_file_not_found_for_missing_markdown(self, tmp_path):
        missing = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError, match="Markdown file not found"):
            export_docx(missing)

    def test_raises_runtime_error_on_pandoc_failure(self, tmp_path):
        md_file = tmp_path / "report.md"
        md_file.write_text("# Report")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Unknown output format docx"

        with patch("morning_report.report.exporter.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="pandoc failed"):
                export_docx(md_file)

    def test_default_output_replaces_suffix(self, tmp_path):
        md_file = tmp_path / "2026-02-25.md"
        md_file.write_text("# Report")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("morning_report.report.exporter.subprocess.run", return_value=mock_result):
            result = export_docx(md_file)

        assert result.suffix == ".docx"
        assert result.stem == "2026-02-25"
