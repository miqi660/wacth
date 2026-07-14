from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

import ultra3_editor.greenlion_builder as builder
from ultra3_editor.cli import main, make_parser


def _files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    image = tmp_path / "image.png"
    Image.new("RGB", (64, 64), (31, 93, 177)).save(image)
    template = tmp_path / "template.bin"
    data = builder.VERIFIED_TEMPLATE_HEADER + bytes(
        builder.STATIC_FILE_SIZE - builder.HEADER_SIZE
    )
    template.write_bytes(data)
    monkeypatch.setattr(
        builder,
        "VERIFIED_TEMPLATE_SHA256",
        hashlib.sha256(data).hexdigest().upper(),
    )
    return image, template, tmp_path / "output.bin"


def test_cli_build_static_diy_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image, template, output = _files(tmp_path, monkeypatch)
    json_path = tmp_path / "build.json"
    report_path = tmp_path / "build.md"
    rc = main(
        [
            "build-static-diy",
            "--image",
            str(image),
            "--template",
            str(template),
            "--output",
            str(output),
            "--json",
            str(json_path),
            "--report",
            str(report_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert "[OK] builder: 0.2.4-greenlion-exact" in captured.out
    assert "[OK] output size: 351617" in captured.out
    assert "[OK] template offset 0: 02" in captured.out
    assert "[OK] exact golden match: not-applicable" in captured.out
    assert "[OK] external usage: 0" in captured.out
    assert output.is_file()
    assert json_path.is_file()
    assert report_path.is_file()


def test_cli_error_is_nonzero_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "build-static-diy",
            "--image",
            str(tmp_path / "missing.png"),
            "--template",
            str(tmp_path / "missing.bin"),
            "--output",
            str(tmp_path / "output.bin"),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "错误:" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "output.bin").exists()


@pytest.mark.parametrize(
    "forbidden",
    (
        "--force",
        "--thumbnail",
        "--time-position",
        "--wire-profile",
        "--quantize",
        "--resample",
        "--fit",
        "--preblur",
    ),
)
def test_cli_does_not_expose_unverified_options(forbidden: str) -> None:
    parser = make_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "build-static-diy",
                "--image",
                "image.png",
                "--template",
                "template.bin",
                "--output",
                "output.bin",
                forbidden,
                "value",
            ]
        )


@pytest.mark.parametrize("missing", ("image", "template", "output"))
def test_cli_requires_all_primary_paths(missing: str) -> None:
    arguments = {
        "image": ["--image", "image.png"],
        "template": ["--template", "template.bin"],
        "output": ["--output", "output.bin"],
    }
    argv = ["build-static-diy"]
    for name, values in arguments.items():
        if name != missing:
            argv.extend(values)
    with pytest.raises(SystemExit):
        make_parser().parse_args(argv)
