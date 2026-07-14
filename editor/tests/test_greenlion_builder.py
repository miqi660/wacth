from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from PIL import Image

import ultra3_editor.greenlion_builder as builder
from ultra3_editor import (
    BuildDeterminismStatus,
    FitMode,
    GoldenBuildStatus,
    GreenLionStaticBuildConfig,
    GreenLionStaticBuildInput,
    ThumbnailMode,
    build_greenlion_static_diy,
)
from ultra3_editor.errors import (
    BuilderInputError,
    BuildInputOutputSamePathError,
    BuildOutputExistsError,
    BuildRollbackError,
    BuildVerificationError,
    InvalidImageError,
    UnsupportedBuilderConfigError,
    UnsupportedImageFormatError,
    UnsupportedPillowVersionError,
    UnsupportedTemplateError,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _make_image(path: Path, *, mode: str = "RGB", fmt: str = "PNG") -> Path:
    color = (23, 117, 209, 180) if mode == "RGBA" else (23, 117, 209)
    image = Image.new(mode, (73, 91), color)
    image.putpixel((0, 0), color)
    image.save(path, format=fmt)
    return path


def _make_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = builder.VERIFIED_TEMPLATE_HEADER + bytes(
        [0x5A]
    ) * (builder.STATIC_FILE_SIZE - builder.HEADER_SIZE)
    path = tmp_path / "template.bin"
    path.write_bytes(data)
    monkeypatch.setattr(builder, "VERIFIED_TEMPLATE_SHA256", _sha256(data))
    return path


def _inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    return (
        _make_image(tmp_path / "image.png"),
        _make_template(tmp_path, monkeypatch),
        tmp_path / "output.bin",
    )


def test_public_build_creates_exact_layout_and_preserves_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    image_before = image.read_bytes()
    template_before = template.read_bytes()

    result = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, output)
    )

    data = output.read_bytes()
    assert len(data) == builder.STATIC_FILE_SIZE
    assert data[: builder.HEADER_SIZE] == template_before[: builder.HEADER_SIZE]
    assert data[0] == 2
    assert image.read_bytes() == image_before
    assert template.read_bytes() == template_before
    assert result.status == "COMPLETE"
    assert result.output_sha256 == _sha256(data)
    assert result.output_revalidated is True
    assert result.image_unchanged is True
    assert result.template_unchanged is True
    assert result.golden_status is GoldenBuildStatus.NOT_APPLICABLE
    assert result.exact_golden_match is None
    assert result.determinism_status is BuildDeterminismStatus.NOT_EVALUATED
    assert result.repeated_build_sha256 is None
    assert result.main_resource_size == (320, 384)
    assert result.thumbnail_resource_size == (210, 252)
    assert [(item.start, item.end) for item in result.replaced_regions] == [
        (17, 245_777),
        (245_777, 351_617),
    ]
    assert all(value == 0 for value in vars(result.external_usage).values())


def test_build_is_deterministic_across_two_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output1 = _inputs(tmp_path, monkeypatch)
    output2 = tmp_path / "output2.bin"
    first = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, output1)
    )
    second = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, output2)
    )
    assert output1.read_bytes() == output2.read_bytes()
    assert first.output_sha256 == second.output_sha256
    assert first.determinism_status is BuildDeterminismStatus.NOT_EVALUATED
    assert second.determinism_status is BuildDeterminismStatus.NOT_EVALUATED
    assert first.repeated_build_sha256 is None
    assert second.repeated_build_sha256 is None


def test_single_build_does_not_claim_repeat_determinism(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    result = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, output)
    )
    assert result.determinism_status is BuildDeterminismStatus.NOT_EVALUATED
    assert result.repeated_build_sha256 is None


def test_custom_build_has_no_boolean_golden_match_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    result = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, output)
    )
    assert result.golden_status is GoldenBuildStatus.NOT_APPLICABLE
    assert result.exact_golden_match is None


def test_serializers_use_stable_status_strings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    result = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, output)
    )
    value = builder.build_result_dict(result)
    markdown = builder.render_build_markdown(result)
    assert value["determinism_status"] == "not_evaluated"
    assert value["golden_status"] == "not_applicable"
    assert "determinism status: `not_evaluated`" in markdown
    assert "golden status: `not_applicable`" in markdown


@pytest.mark.parametrize(("mode", "fmt"), (("RGB", "PNG"), ("RGBA", "PNG"), ("RGB", "JPEG")))
def test_supported_image_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    fmt: str,
) -> None:
    suffix = ".jpg" if fmt == "JPEG" else ".png"
    image = _make_image(tmp_path / f"image{suffix}", mode=mode, fmt=fmt)
    template = _make_template(tmp_path, monkeypatch)
    result = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, tmp_path / "out.bin")
    )
    assert result.image_format == fmt


def test_thumbnail_is_generated_independently_from_same_source() -> None:
    image = Image.new("RGB", (600, 200))
    for x in range(600):
        for y in range(200):
            image.putpixel((x, y), (x % 256, y, (x + y) % 256))
    main = builder._fit_cover_exact(image, builder.MAIN_RESOURCE_SIZE)
    thumbnail = builder._fit_cover_exact(image, builder.THUMBNAIL_RESOURCE_SIZE)
    assert main.size == (320, 384)
    assert thumbnail.size == (210, 252)
    assert thumbnail != main.resize((210, 252), Image.Resampling.BILINEAR)


def test_rgb565_truncate_and_next_high_vectors() -> None:
    image = Image.new("RGB", (3, 1))
    image.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255)])
    normal = builder._image_to_rgb565_le_exact(image)
    assert normal.hex().upper() == "00F8E0071F00"
    assert builder._apply_greenlion_next_high(normal).hex().upper() == "0007E0001F00"


def test_json_and_markdown_are_core_generated_and_path_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    json_path = tmp_path / "build.json"
    report_path = tmp_path / "build.md"
    result = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, output),
        json_path=json_path,
        report_path=report_path,
    )
    value = json.loads(json_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")
    assert value["output_sha256"] == result.output_sha256
    assert value["golden_status"] == "not_applicable"
    assert value["determinism_status"] == "not_evaluated"
    assert value["exact_golden_match"] is None
    assert value["repeated_build_sha256"] is None
    assert value["image_path"] == image.name
    assert value["template_path"] == template.name
    assert value["output_path"] == output.name
    assert str(tmp_path) not in json_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in report
    assert "外部设备调用：`0`" in report
    assert "golden status: `not_applicable`" in report
    assert "determinism status: `not_evaluated`" in report


@pytest.mark.parametrize("missing", ("image", "template"))
def test_missing_input_is_rejected_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    image = _make_image(tmp_path / "image.png")
    template = _make_template(tmp_path, monkeypatch)
    if missing == "image":
        image.unlink()
    else:
        template.unlink()
    output = tmp_path / "out.bin"
    with pytest.raises(BuilderInputError) as exc_info:
        build_greenlion_static_diy(GreenLionStaticBuildInput(image, template, output))
    assert exc_info.value.error_code == "builder_input_error"
    assert not output.exists()


def test_invalid_image_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"not an image")
    template = _make_template(tmp_path, monkeypatch)
    with pytest.raises(InvalidImageError):
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, tmp_path / "out.bin")
        )


def test_unsupported_image_container_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = _make_image(tmp_path / "image.bmp", fmt="BMP")
    template = _make_template(tmp_path, monkeypatch)
    with pytest.raises(UnsupportedImageFormatError) as exc_info:
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, tmp_path / "out.bin")
        )
    assert exc_info.value.expected == "PNG|JPEG"
    assert exc_info.value.actual == "BMP"


@pytest.mark.parametrize("kind", ("size", "header", "hash"))
def test_invalid_template_is_rejected_with_structured_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    image = _make_image(tmp_path / "image.png")
    template = _make_template(tmp_path, monkeypatch)
    data = bytearray(template.read_bytes())
    if kind == "size":
        data.pop()
    elif kind == "header":
        data[0] = 1
    else:
        data[-1] ^= 1
    template.write_bytes(data)
    output = tmp_path / "out.bin"
    with pytest.raises(UnsupportedTemplateError) as exc_info:
        build_greenlion_static_diy(GreenLionStaticBuildInput(image, template, output))
    assert exc_info.value.path == template
    assert exc_info.value.expected is not None
    assert exc_info.value.actual is not None
    assert not output.exists()


@pytest.mark.parametrize(
    "config",
    (
        GreenLionStaticBuildConfig(fit_mode=FitMode.STRETCH),
        GreenLionStaticBuildConfig(fit_mode=FitMode.CONTAIN),
        GreenLionStaticBuildConfig(thumbnail_mode=ThumbnailMode.PRESERVE_TEMPLATE),
    ),
)
def test_non_exact_config_is_rejected_without_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config: GreenLionStaticBuildConfig,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    with pytest.raises(UnsupportedBuilderConfigError):
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, output), config=config
        )
    assert not output.exists()


def test_wrong_pillow_version_is_rejected_before_reading_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder, "pillow_version", "10.3.0")
    with pytest.raises(UnsupportedPillowVersionError) as exc_info:
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(
                tmp_path / "missing.png", tmp_path / "missing.bin", tmp_path / "out.bin"
            )
        )
    assert exc_info.value.expected == "10.4.0"
    assert exc_info.value.actual == "10.3.0"


@pytest.mark.parametrize("existing", ("output", "json", "report"))
def test_existing_target_is_never_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: str,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    paths = {"output": output, "json": tmp_path / "build.json", "report": tmp_path / "build.md"}
    paths[existing].write_text("保留", encoding="utf-8")
    with pytest.raises(BuildOutputExistsError):
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, output),
            json_path=paths["json"],
            report_path=paths["report"],
        )
    assert paths[existing].read_text(encoding="utf-8") == "保留"


@pytest.mark.parametrize("target", ("image", "template", "duplicate"))
def test_conflicting_paths_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    if target == "image":
        output = image
        json_path = None
    elif target == "template":
        output = template
        json_path = None
    else:
        json_path = output
    with pytest.raises(BuildInputOutputSamePathError):
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, output), json_path=json_path
        )


def test_writeback_failure_removes_current_call_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(builder, "_read_written_output", lambda path: b"corrupt")
    with pytest.raises(BuildVerificationError):
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, output),
            json_path=tmp_path / "build.json",
            report_path=tmp_path / "build.md",
        )
    assert not output.exists()
    assert not (tmp_path / "build.json").exists()
    assert not (tmp_path / "build.md").exists()


def test_report_failure_rolls_back_bin_and_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    original = builder._write_text_exclusive

    def fail_markdown(path: Path, text: str) -> None:
        if path.suffix == ".md":
            raise BuildVerificationError("模拟报告失败")
        original(path, text)

    monkeypatch.setattr(builder, "_write_text_exclusive", fail_markdown)
    with pytest.raises(BuildVerificationError):
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, output),
            json_path=tmp_path / "build.json",
            report_path=tmp_path / "build.md",
        )
    assert not output.exists()
    assert not (tmp_path / "build.json").exists()


def test_known_golden_mismatch_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(builder, "_GOLDEN_OUTPUTS", {_sha256(image.read_bytes()): "0" * 64})
    with pytest.raises(BuildVerificationError, match="黄金") as exc_info:
        build_greenlion_static_diy(GreenLionStaticBuildInput(image, template, output))
    assert exc_info.value.golden_status is GoldenBuildStatus.MISMATCH
    assert exc_info.value.expected == "0" * 64
    assert exc_info.value.actual is not None
    assert not output.exists()


def test_known_golden_match_uses_stable_enum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, first_output = _inputs(tmp_path, monkeypatch)
    first = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, first_output)
    )
    monkeypatch.setattr(
        builder,
        "_GOLDEN_OUTPUTS",
        {_sha256(image.read_bytes()): first.output_sha256},
    )
    result = build_greenlion_static_diy(
        GreenLionStaticBuildInput(image, template, tmp_path / "second.bin")
    )
    assert result.golden_status is GoldenBuildStatus.MATCH
    assert result.exact_golden_match is True


def test_main_output_cleanup_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(builder, "_read_written_output", lambda path: b"corrupt")
    original_unlink = Path.unlink

    def fail_output(self: Path, *args: object, **kwargs: object) -> None:
        if self == output:
            raise OSError("模拟主输出清理失败")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_output)
    with pytest.raises(BuildRollbackError) as exc_info:
        build_greenlion_static_diy(GreenLionStaticBuildInput(image, template, output))
    assert exc_info.value.original_error_type == "BuildVerificationError"
    assert output in exc_info.value.failed_cleanup_paths
    assert exc_info.value.__cause__ is not None


def test_json_cleanup_failure_is_reported_and_other_created_file_is_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    json_path = tmp_path / "build.json"
    report_path = tmp_path / "build.md"
    original_write = builder._write_text_exclusive
    original_unlink = Path.unlink

    def fail_report(path: Path, text: str) -> None:
        if path == report_path:
            raise BuildVerificationError("模拟 Markdown 失败")
        original_write(path, text)

    def fail_json(self: Path, *args: object, **kwargs: object) -> None:
        if self == json_path:
            raise OSError("模拟 JSON 清理失败")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(builder, "_write_text_exclusive", fail_report)
    monkeypatch.setattr(Path, "unlink", fail_json)
    with pytest.raises(BuildRollbackError) as exc_info:
        build_greenlion_static_diy(
            GreenLionStaticBuildInput(image, template, output),
            json_path=json_path,
            report_path=report_path,
        )
    assert exc_info.value.failed_cleanup_paths == (json_path,)
    assert json_path.exists()
    assert not output.exists()


class _FailingWriter:
    def __enter__(self) -> "_FailingWriter":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def write(self, value: object) -> None:
        raise OSError("模拟部分写入失败")


@pytest.mark.parametrize(
    ("suffix", "writer_name", "value"),
    ((".bin", "_write_binary_exclusive", b"data"), (".md", "_write_text_exclusive", "data")),
)
def test_partial_write_cleanup_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    writer_name: str,
    value: bytes | str,
) -> None:
    path = tmp_path / f"partial{suffix}"
    original_open = Path.open
    original_unlink = Path.unlink

    def failing_open(self: Path, *args: object, **kwargs: object) -> object:
        if self == path:
            path.touch()
            return _FailingWriter()
        return original_open(self, *args, **kwargs)

    def failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == path:
            raise OSError("模拟部分文件清理失败")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    monkeypatch.setattr(Path, "unlink", failing_unlink)
    with pytest.raises(BuildRollbackError) as exc_info:
        getattr(builder, writer_name)(path, value)
    assert exc_info.value.original_error_type == "OSError"
    assert exc_info.value.original_error_message == "模拟部分写入失败"
    assert exc_info.value.failed_cleanup_paths == (path,)
    assert exc_info.value.error_code == "build_rollback_error"


def test_rollback_only_touches_files_created_by_current_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)
    protected = tmp_path / "protected.txt"
    protected.write_text("保留", encoding="utf-8")
    calls: list[Path] = []
    original_unlink = Path.unlink

    def track_unlink(self: Path, *args: object, **kwargs: object) -> None:
        calls.append(self)
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(builder, "_read_written_output", lambda path: b"corrupt")
    monkeypatch.setattr(Path, "unlink", track_unlink)
    with pytest.raises(BuildVerificationError):
        build_greenlion_static_diy(GreenLionStaticBuildInput(image, template, output))
    assert protected.read_text(encoding="utf-8") == "保留"
    assert calls == [output]


@pytest.mark.parametrize("interrupt", (KeyboardInterrupt, SystemExit))
def test_control_flow_exceptions_are_not_swallowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt: type[BaseException],
) -> None:
    image, template, output = _inputs(tmp_path, monkeypatch)

    def stop(path: Path) -> bytes:
        raise interrupt("停止")

    monkeypatch.setattr(builder, "_read_written_output", stop)
    with pytest.raises(interrupt):
        build_greenlion_static_diy(GreenLionStaticBuildInput(image, template, output))


def test_models_are_immutable(tmp_path: Path) -> None:
    value = GreenLionStaticBuildInput(tmp_path / "a", tmp_path / "b", tmp_path / "c")
    with pytest.raises(FrozenInstanceError):
        value.output_path = tmp_path / "d"  # type: ignore[misc]


def test_public_exports_are_available() -> None:
    import ultra3_editor

    assert ultra3_editor.build_greenlion_static_diy is build_greenlion_static_diy
    assert ultra3_editor.GreenLionStaticBuildInput is GreenLionStaticBuildInput


def test_builder_has_no_external_or_time_editor_imports() -> None:
    path = ROOT / "src" / "ultra3_editor" / "greenlion_builder.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(
        name == forbidden or name.startswith(forbidden + ".")
        for name in imports
        for forbidden in ("subprocess", "socket", "requests", "urllib")
    )
    for forbidden in ("payload_353146", "set_time_position", "data[0]", "shell=True"):
        assert forbidden not in source
