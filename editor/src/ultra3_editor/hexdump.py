from __future__ import annotations


def hex_bytes(data: bytes) -> str:
    return data.hex(" ").upper()


def format_hexdump(data: bytes, *, start_offset: int = 0, width: int = 16) -> str:
    lines: list[str] = []
    for index in range(0, len(data), width):
        chunk = data[index : index + width]
        hex_part = " ".join(f"{value:02X}" for value in chunk)
        ascii_part = "".join(chr(value) if 32 <= value <= 126 else "." for value in chunk)
        lines.append(
            f"{start_offset + index:08X}  {hex_part:<{width * 3 - 1}}  |{ascii_part}|"
        )
    return "\n".join(lines)
