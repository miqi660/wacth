from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError, __version__ as pillow_version

from .errors import (
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


BUILDER_VERSION = "0.2.4-greenlion-exact"
SUPPORTED_PILLOW_VERSION = "10.4.0"
STATIC_FILE_SIZE = 351_617
HEADER_SIZE = 17
MAIN_RESOURCE_SIZE = (320, 384)
THUMBNAIL_RESOURCE_SIZE = (210, 252)
MAIN_BYTE_SIZE = MAIN_RESOURCE_SIZE[0] * MAIN_RESOURCE_SIZE[1] * 2
THUMBNAIL_BYTE_SIZE = THUMBNAIL_RESOURCE_SIZE[0] * THUMBNAIL_RESOURCE_SIZE[1] * 2
VERIFIED_TEMPLATE_SHA256 = (
    "5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC"
)
VERIFIED_TEMPLATE_HEADER = bytes.fromhex(
    "02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00"
)

_GOLDEN_OUTPUTS = {
    "9FDBB04E9DD910296B44BECB98C25A0C988A4B1B98EC0DAE12A0E831BC747CB4":
        "44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664",
    "993BE3445975504C1BD2E587E38D5E22F421305161FEEBCCB8C1AE0BEA638ACD":
        "CBD34D9BE77B138481AB7AD590326CC7437EE55C45DBECB532A0DF1C4F8A2763",
    "158C38A2E0713B7B1AE5F24A346C24A72102A1F2E3FD49ACA71DB5CAD8D2A6E5":
        "19CAF5303D780FD6C4F46DED3219AD41E839FD495A1A96C51FD40EAE296C23B6",
    "8AA6F1830BE27CDC86DCE7A44997B6FD32EBF4A419E5F74A6420C579870C8BE7":
        "7F1F531F94E6C312FFEF167B03B2988AAC44A42790ABA19A6EED9F03795344C9",
    "0748AA" "DB7C9B20D99C78C4165E77B0129B8554AB331F670886E3D0BD3F3E6828":
        "62E2B481F62C270937E090AD69CC87A34A11B7DDBEFFCA1B70D31AE638CB4078",
}


class FitMode(str, Enum):
    COVER = "cover"
    STRETCH = "stretch"
    CONTAIN = "contain"


class ThumbnailMode(str, Enum):
    AUTO_FROM_MAIN = "auto-from-main"
    PRESERVE_TEMPLATE = "preserve-template"


class BuildDeterminismStatus(str, Enum):
    NOT_EVALUATED = "not_evaluated"
    VERIFIED_REPEAT = "verified_repeat"


class GoldenBuildStatus(str, Enum):
    MATCH = "match"
    NOT_APPLICABLE = "not_applicable"
    MISMATCH = "mismatch"


@dataclass(frozen=True)
class GreenLionStaticBuildInput:
    image_path: Path
    template_path: Path
    output_path: Path


@dataclass(frozen=True)
class GreenLionStaticBuildConfig:
    fit_mode: FitMode = FitMode.COVER
    thumbnail_mode: ThumbnailMode = ThumbnailMode.AUTO_FROM_MAIN


@dataclass(frozen=True)
class BuildRegion:
    name: str
    start: int
    end: int
    length: int


@dataclass(frozen=True)
class ExternalUsage:
    hardware_initializations: int = 0
    hardware_scans: int = 0
    hardware_connections: int = 0
    hardware_writes: int = 0
    external_processes: int = 0
    network_operations: int = 0
    real_uploads: int = 0


@dataclass(frozen=True)
class GreenLionStaticBuildResult:
    status: str
    builder_version: str
    container: str
    firmware_scope: str
    image_path: Path
    image_format: str
    image_size: int
    image_sha256_before: str
    image_sha256_after: str
    image_unchanged: bool
    template_path: Path
    template_size: int
    template_sha256_before: str
    template_sha256_after: str
    template_unchanged: bool
    template_header_hex: str
    template_header_preserved: bool
    template_offset_zero: int
    output_path: Path
    output_size: int
    output_sha256: str
    output_revalidated: bool
    main_resource_size: tuple[int, int]
    thumbnail_resource_size: tuple[int, int]
    fit_mode: FitMode
    thumbnail_mode: ThumbnailMode
    resample: str
    quantize: str
    wire_profile: str
    preblur: float
    replaced_regions: tuple[BuildRegion, ...]
    determinism_status: BuildDeterminismStatus
    repeated_build_sha256: str | None
    golden_status: GoldenBuildStatus
    exact_golden_match: bool | None
    golden_target_sha256: str | None
    external_usage: ExternalUsage
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


def build_greenlion_static_diy(
    build_input: GreenLionStaticBuildInput,
    *,
    config: GreenLionStaticBuildConfig = GreenLionStaticBuildConfig(),
    json_path: Path | None = None,
    report_path: Path | None = None,
) -> GreenLionStaticBuildResult:
    _validate_runtime()
    _validate_config(config)

    image_path = Path(build_input.image_path)
    template_path = Path(build_input.template_path)
    output_path = Path(build_input.output_path)
    json_output = Path(json_path) if json_path is not None else None
    report_output = Path(report_path) if report_path is not None else None
    targets = [path for path in (output_path, json_output, report_output) if path is not None]
    _validate_paths(image_path, template_path, targets)

    image_bytes = _read_input(image_path, "图片")
    template = _read_input(template_path, "模板")
    image_sha256 = _sha256(image_bytes)
    template_sha256 = _validate_template(template_path, template)
    source, image_format = _open_image(image_path)

    main_image = _fit_cover_exact(source, MAIN_RESOURCE_SIZE)
    thumbnail_image = _fit_cover_exact(source, THUMBNAIL_RESOURCE_SIZE)
    main_bytes = _apply_greenlion_next_high(_image_to_rgb565_le_exact(main_image))
    thumbnail_bytes = _apply_greenlion_next_high(
        _image_to_rgb565_le_exact(thumbnail_image)
    )
    output_bytes = template[:HEADER_SIZE] + main_bytes + thumbnail_bytes
    calculated_output_sha256 = _validate_in_memory_output(
        output_bytes,
        template,
        main_bytes,
        thumbnail_bytes,
    )
    golden_target = _GOLDEN_OUTPUTS.get(image_sha256)
    if golden_target is not None and calculated_output_sha256 != golden_target:
        raise BuildVerificationError(
            "已知黄金输入的构建结果不匹配",
            path=output_path,
            expected=golden_target,
            actual=calculated_output_sha256,
            golden_status=GoldenBuildStatus.MISMATCH,
        )

    created: list[Path] = []
    try:
        _prepare_parents(targets)
        _write_binary_exclusive(output_path, output_bytes)
        created.append(output_path)
        written = _read_written_output(output_path)
        _validate_written_output(
            output_path,
            written,
            output_bytes,
            template,
            main_bytes,
            thumbnail_bytes,
        )

        image_sha256_after = _sha256_file(image_path, "图片")
        template_sha256_after = _sha256_file(template_path, "模板")
        if image_sha256_after != image_sha256:
            raise BuildVerificationError(
                "输入图片在构建过程中发生变化",
                path=image_path,
                expected=image_sha256,
                actual=image_sha256_after,
            )
        if template_sha256_after != template_sha256:
            raise BuildVerificationError(
                "模板在构建过程中发生变化",
                path=template_path,
                expected=template_sha256,
                actual=template_sha256_after,
            )

        result = GreenLionStaticBuildResult(
            status="COMPLETE",
            builder_version=BUILDER_VERSION,
            container="greenlion-static",
            firmware_scope="NJ-LEJ-2.1.7",
            image_path=image_path.resolve(),
            image_format=image_format,
            image_size=len(image_bytes),
            image_sha256_before=image_sha256,
            image_sha256_after=image_sha256_after,
            image_unchanged=True,
            template_path=template_path.resolve(),
            template_size=len(template),
            template_sha256_before=template_sha256,
            template_sha256_after=template_sha256_after,
            template_unchanged=True,
            template_header_hex=template[:HEADER_SIZE].hex(" ").upper(),
            template_header_preserved=True,
            template_offset_zero=output_bytes[0],
            output_path=output_path.resolve(),
            output_size=len(written),
            output_sha256=calculated_output_sha256,
            output_revalidated=True,
            main_resource_size=MAIN_RESOURCE_SIZE,
            thumbnail_resource_size=THUMBNAIL_RESOURCE_SIZE,
            fit_mode=config.fit_mode,
            thumbnail_mode=config.thumbnail_mode,
            resample="bilinear",
            quantize="truncate",
            wire_profile="greenlion-next-high",
            preblur=0.0,
            replaced_regions=(
                BuildRegion("main", HEADER_SIZE, HEADER_SIZE + MAIN_BYTE_SIZE, MAIN_BYTE_SIZE),
                BuildRegion(
                    "thumbnail",
                    HEADER_SIZE + MAIN_BYTE_SIZE,
                    STATIC_FILE_SIZE,
                    THUMBNAIL_BYTE_SIZE,
                ),
            ),
            determinism_status=BuildDeterminismStatus.NOT_EVALUATED,
            repeated_build_sha256=None,
            golden_status=(
                GoldenBuildStatus.MATCH
                if golden_target is not None
                else GoldenBuildStatus.NOT_APPLICABLE
            ),
            exact_golden_match=True if golden_target is not None else None,
            golden_target_sha256=golden_target,
            external_usage=ExternalUsage(),
            warnings=(),
            errors=(),
        )

        if json_output is not None:
            _write_text_exclusive(
                json_output,
                json.dumps(build_result_dict(result), ensure_ascii=False, indent=2) + "\n",
            )
            created.append(json_output)
        if report_output is not None:
            _write_text_exclusive(report_output, render_build_markdown(result))
            created.append(report_output)
        return result
    except Exception as exc:
        failed_cleanup_paths = _cleanup_created(created)
        if failed_cleanup_paths:
            raise BuildRollbackError(exc, failed_cleanup_paths) from exc
        raise


def build_result_dict(result: GreenLionStaticBuildResult) -> dict[str, Any]:
    value = asdict(result)
    value["image_path"] = result.image_path.name
    value["template_path"] = result.template_path.name
    value["output_path"] = result.output_path.name
    value["fit_mode"] = result.fit_mode.value
    value["thumbnail_mode"] = result.thumbnail_mode.value
    value["determinism_status"] = result.determinism_status.value
    value["golden_status"] = result.golden_status.value
    value["main_resource_size"] = list(result.main_resource_size)
    value["thumbnail_resource_size"] = list(result.thumbnail_resource_size)
    return value


def render_build_markdown(result: GreenLionStaticBuildResult) -> str:
    golden = "true" if result.exact_golden_match is True else "null"
    target = result.golden_target_sha256 or "NOT_APPLICABLE"
    repeated = result.repeated_build_sha256 or "NOT_EVALUATED"
    return "\n".join(
        (
            "# GreenLion Static DIY 构建记录",
            "",
            f"- status: `{result.status}`",
            f"- builder version: `{result.builder_version}`",
            f"- container: `{result.container}`",
            f"- firmware scope: `{result.firmware_scope}`",
            f"- image: `{result.image_path.name}`",
            f"- image format: `{result.image_format}`",
            f"- image SHA-256: `{result.image_sha256_before}`",
            f"- template: `{result.template_path.name}`",
            f"- template SHA-256: `{result.template_sha256_before}`",
            f"- template unchanged: `{str(result.template_unchanged).lower()}`",
            f"- template header preserved: `{str(result.template_header_preserved).lower()}`",
            f"- template offset 0: `{result.template_offset_zero:02X}`",
            f"- output: `{result.output_path.name}`",
            f"- output size: `{result.output_size}`",
            f"- output SHA-256: `{result.output_sha256}`",
            f"- output revalidated: `{str(result.output_revalidated).lower()}`",
            f"- main resource: `{result.main_resource_size[0]}x{result.main_resource_size[1]}`",
            f"- thumbnail resource: `{result.thumbnail_resource_size[0]}x{result.thumbnail_resource_size[1]}`",
            f"- fit: `{result.fit_mode.value}`",
            f"- resample: `{result.resample}`",
            f"- quantize: `{result.quantize}`",
            f"- wire profile: `{result.wire_profile}`",
            f"- determinism status: `{result.determinism_status.value}`",
            f"- repeated build SHA-256: `{repeated}`",
            f"- golden status: `{result.golden_status.value}`",
            f"- exact golden match: `{golden}`",
            f"- golden target SHA-256: `{target}`",
            "",
            "## 安全边界",
            "",
            "- 外部设备调用：`0`",
            "- 网络请求：`0`",
            "- 真实上传：`0`",
            "- GUI：未接入",
            "- 时间位置编辑：未调用",
            "- 输入图片与模板：只读并复核 SHA-256",
            "",
        )
    )


def _validate_runtime() -> None:
    if pillow_version != SUPPORTED_PILLOW_VERSION:
        raise UnsupportedPillowVersionError(
            "Pillow 版本不在 exact 范围",
            expected=SUPPORTED_PILLOW_VERSION,
            actual=pillow_version,
        )


def _validate_config(config: GreenLionStaticBuildConfig) -> None:
    if not isinstance(config, GreenLionStaticBuildConfig):
        raise UnsupportedBuilderConfigError(
            "config 必须是 GreenLionStaticBuildConfig",
            expected="GreenLionStaticBuildConfig",
            actual=type(config).__name__,
        )
    if config.fit_mode is not FitMode.COVER:
        raise UnsupportedBuilderConfigError(
            "Stage 8B-1 只支持 cover",
            expected=FitMode.COVER.value,
            actual=getattr(config.fit_mode, "value", config.fit_mode),
        )
    if config.thumbnail_mode is not ThumbnailMode.AUTO_FROM_MAIN:
        raise UnsupportedBuilderConfigError(
            "Stage 8B-1 只支持从同一输入图片独立生成缩略图",
            expected=ThumbnailMode.AUTO_FROM_MAIN.value,
            actual=getattr(config.thumbnail_mode, "value", config.thumbnail_mode),
        )


def _read_input(path: Path, label: str) -> bytes:
    if not path.is_file():
        raise BuilderInputError(
            f"{label}不存在或不是普通文件: {path}",
            path=path,
            expected="regular_file",
            actual="missing_or_non_file",
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise BuilderInputError(f"无法读取{label}: {path}", path=path) from exc


def _open_image(path: Path) -> tuple[Image.Image, str]:
    try:
        with Image.open(path) as opened:
            image_format = (opened.format or "").upper()
            if image_format not in {"PNG", "JPEG"}:
                raise UnsupportedImageFormatError(
                    "只支持经验证的 PNG 或 JPEG 图片",
                    path=path,
                    expected="PNG|JPEG",
                    actual=image_format or "UNKNOWN",
                )
            opened.load()
            return opened.convert("RGB"), image_format
    except UnsupportedImageFormatError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("图片无法解码", path=path, actual=type(exc).__name__) from exc


def _validate_template(path: Path, template: bytes) -> str:
    if len(template) != STATIC_FILE_SIZE:
        raise UnsupportedTemplateError(
            "模板大小不在 exact 范围",
            path=path,
            expected=STATIC_FILE_SIZE,
            actual=len(template),
        )
    header = template[:HEADER_SIZE]
    if header != VERIFIED_TEMPLATE_HEADER:
        raise UnsupportedTemplateError(
            "模板头不匹配",
            path=path,
            expected=VERIFIED_TEMPLATE_HEADER.hex(" ").upper(),
            actual=header.hex(" ").upper(),
        )
    digest = _sha256(template)
    if digest != VERIFIED_TEMPLATE_SHA256:
        raise UnsupportedTemplateError(
            "模板 SHA-256 不匹配",
            path=path,
            expected=VERIFIED_TEMPLATE_SHA256,
            actual=digest,
        )
    return digest


def _fit_cover_exact(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB")
    source_w, source_h = image.size
    if source_w <= 0 or source_h <= 0:
        raise InvalidImageError(
            "图片尺寸无效",
            expected="positive_dimensions",
            actual=image.size,
        )
    target_w, target_h = size
    scale = max(target_w / source_w, target_h / source_h)
    resized_w = max(1, round(source_w * scale))
    resized_h = max(1, round(source_h * scale))
    resized = image.resize((resized_w, resized_h), Image.Resampling.BILINEAR)
    left = (resized_w - target_w) // 2
    top = (resized_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _image_to_rgb565_le_exact(image: Image.Image) -> bytes:
    output = bytearray()
    for red, green, blue in image.convert("RGB").getdata():
        word = ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)
        output.append(word & 0xFF)
        output.append((word >> 8) & 0xFF)
    return bytes(output)


def _apply_greenlion_next_high(normal: bytes) -> bytes:
    if len(normal) % 2:
        raise BuildVerificationError(
            "RGB565 缓冲区长度必须为偶数",
            expected="even",
            actual=len(normal),
        )
    output = bytearray(len(normal))
    pixels = len(normal) // 2
    for index in range(pixels):
        output[index * 2] = normal[index * 2]
        output[index * 2 + 1] = normal[(index + 1) * 2 + 1] if index + 1 < pixels else 0
    return bytes(output)


def _validate_in_memory_output(
    output: bytes,
    template: bytes,
    main: bytes,
    thumbnail: bytes,
) -> str:
    if len(main) != MAIN_BYTE_SIZE or len(thumbnail) != THUMBNAIL_BYTE_SIZE:
        raise BuildVerificationError(
            "资源长度复核失败",
            expected=(MAIN_BYTE_SIZE, THUMBNAIL_BYTE_SIZE),
            actual=(len(main), len(thumbnail)),
        )
    if len(output) != STATIC_FILE_SIZE:
        raise BuildVerificationError(
            "构建结果大小复核失败",
            expected=STATIC_FILE_SIZE,
            actual=len(output),
        )
    if output[:HEADER_SIZE] != template[:HEADER_SIZE] or output[0] != 2:
        raise BuildVerificationError(
            "模板头未被完整保留",
            expected=template[:HEADER_SIZE].hex(" ").upper(),
            actual=output[:HEADER_SIZE].hex(" ").upper(),
        )
    return _sha256(output)


def _validate_written_output(
    path: Path,
    written: bytes,
    expected_output: bytes,
    template: bytes,
    main: bytes,
    thumbnail: bytes,
) -> None:
    if written != expected_output:
        raise BuildVerificationError(
            "写后逐字节复核失败",
            path=path,
            expected=_sha256(expected_output),
            actual=_sha256(written),
        )
    _validate_in_memory_output(written, template, main, thumbnail)


def _validate_paths(image: Path, template: Path, targets: list[Path]) -> None:
    input_keys = {_path_key(image), _path_key(template)}
    target_keys = [_path_key(path) for path in targets]
    if input_keys.intersection(target_keys):
        raise BuildInputOutputSamePathError("输入图片或模板不能同时作为输出目标")
    if len(set(target_keys)) != len(target_keys):
        raise BuildInputOutputSamePathError("输出 BIN、JSON 和 Markdown 路径不能重复")
    for path in targets:
        if path.exists():
            raise BuildOutputExistsError(
                f"输出目标已存在，拒绝覆盖: {path}",
                path=path,
                expected="not_exists",
                actual="exists",
            )


def _prepare_parents(targets: list[Path]) -> None:
    try:
        for path in targets:
            path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BuildVerificationError("无法创建输出目录") from exc


def _write_binary_exclusive(path: Path, data: bytes) -> None:
    created = False
    try:
        with path.open("xb") as stream:
            created = True
            stream.write(data)
    except FileExistsError as exc:
        raise BuildOutputExistsError(
            f"输出目标已存在，拒绝覆盖: {path}", path=path
        ) from exc
    except OSError as exc:
        if created:
            failed_cleanup_paths = _cleanup_created([path])
            if failed_cleanup_paths:
                raise BuildRollbackError(exc, failed_cleanup_paths) from exc
        raise BuildVerificationError("无法写入构建结果", path=path) from exc


def _write_text_exclusive(path: Path, text: str) -> None:
    created = False
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(text)
    except FileExistsError as exc:
        raise BuildOutputExistsError(
            f"输出目标已存在，拒绝覆盖: {path}", path=path
        ) from exc
    except OSError as exc:
        if created:
            failed_cleanup_paths = _cleanup_created([path])
            if failed_cleanup_paths:
                raise BuildRollbackError(exc, failed_cleanup_paths) from exc
        raise BuildVerificationError("无法写入构建报告", path=path) from exc


def _cleanup_created(paths: list[Path]) -> tuple[Path, ...]:
    failed: list[Path] = []
    for path in reversed(paths):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            failed.append(path)
    return tuple(failed)


def _read_written_output(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise BuildVerificationError("无法回读构建结果", path=path) from exc


def _sha256_file(path: Path, label: str) -> str:
    try:
        return _sha256(path.read_bytes())
    except OSError as exc:
        raise BuildVerificationError(f"无法复核{label}", path=path) from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))
