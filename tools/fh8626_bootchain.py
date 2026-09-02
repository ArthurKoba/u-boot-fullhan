#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
"""Create FH8626V100 U-Boot partition and NOR release artifacts."""

import argparse
import binascii
import pathlib
import struct


BOOTSTRAP_SIZE = 0x10000
ENVIRONMENT_OFFSET = 0x10000
ENVIRONMENT_SIZE = 0x10000
UBOOT_DESC = 0x140
UBOOT_OFFSET = 0x20000
UBOOT_SLOT_SIZE = 0x30000
BOOT_REGION_SIZE = UBOOT_OFFSET + UBOOT_SLOT_SIZE
FLASH_SIZE = 0x800000
ALIGNMENT = 0x80


def u32(buf: bytes, offset: int) -> int:
    """Read a little-endian 32-bit integer from *buf*."""
    return struct.unpack_from("<I", buf, offset)[0]


def put_u32(buf: bytearray, offset: int, value: int) -> None:
    """Write a little-endian 32-bit integer to *buf*."""
    struct.pack_into("<I", buf, offset, value)


def jamcrc(data: bytes) -> int:
    """Return the JAMCRC variant used by the FH8626 bootstrap."""
    return binascii.crc32(data) ^ 0xffffffff


def build_partition(image: bytes) -> tuple[bytes, int, int]:
    """Return a padded U-Boot partition, aligned size and bootstrap CRC."""
    if not image:
        raise ValueError("U-Boot image is empty")

    aligned = (len(image) + ALIGNMENT - 1) & ~(ALIGNMENT - 1)
    if aligned > UBOOT_SLOT_SIZE:
        raise ValueError(
            f"U-Boot aligned size {aligned:#x} exceeds slot "
            f"{UBOOT_SLOT_SIZE:#x}"
        )

    partition = bytearray(b"\xff" * UBOOT_SLOT_SIZE)
    partition[:len(image)] = image
    partition[len(image):aligned] = b"\0" * (aligned - len(image))
    return bytes(partition), aligned, jamcrc(partition[:aligned])


def validate_flash_backup(flash: bytes) -> tuple[int, int]:
    """Validate an 8 MiB dump and return its U-Boot geometry."""
    if len(flash) != FLASH_SIZE:
        raise ValueError(
            f"flash backup is {len(flash):#x}, expected {FLASH_SIZE:#x}"
        )
    if flash[:4] != b"2BL*":
        raise ValueError("invalid FH8626 bootstrap magic")
    if flash[UBOOT_DESC:UBOOT_DESC + 16].rstrip(b"\0") != b"uboot":
        raise ValueError("U-Boot descriptor not found at 0x140")
    if u32(flash, UBOOT_DESC + 0x24) != UBOOT_OFFSET:
        raise ValueError("unexpected stock U-Boot flash offset")
    if u32(flash, UBOOT_DESC + 0x28) != 0xa0800000:
        raise ValueError("unexpected stock U-Boot load address")
    if u32(flash, UBOOT_DESC + 0x2c) != 0xa0800000:
        raise ValueError("unexpected stock U-Boot entry address")

    old_aligned = u32(flash, UBOOT_DESC + 0x20)
    if not old_aligned or old_aligned > UBOOT_SLOT_SIZE:
        raise ValueError("invalid U-Boot size in bootstrap descriptor")

    old_checksum = u32(flash, UBOOT_DESC + 0x34)
    old_payload = flash[UBOOT_OFFSET:UBOOT_OFFSET + old_aligned]
    calculated = jamcrc(old_payload)
    if calculated != old_checksum:
        raise ValueError(
            f"stock JAMCRC mismatch: descriptor {old_checksum:#010x}, "
            f"calculated {calculated:#010x}"
        )

    return old_aligned, old_checksum


def write_artifacts(
    image: bytes, output_dir: pathlib.Path, flash: bytes | None = None
) -> None:
    """Write the open partition and optional bootstrap-dependent artifacts."""
    partition, aligned, checksum = build_partition(image)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "u-boot-fh8626v100-partition.bin").write_bytes(partition)

    print(f"new size:      {len(image):#010x}")
    print(f"new aligned:   {aligned:#010x}")
    print(f"new JAMCRC:    {checksum:#010x}")
    print(f"slot spare:    {UBOOT_SLOT_SIZE - aligned:#010x}")

    if flash is None:
        print("bootstrap:     not supplied; skipping full NOR image")
        return

    old_aligned, old_checksum = validate_flash_backup(flash)
    bootstrap = bytearray(flash[:BOOTSTRAP_SIZE])
    put_u32(bootstrap, UBOOT_DESC + 0x18, len(image))
    put_u32(bootstrap, UBOOT_DESC + 0x20, aligned)
    put_u32(bootstrap, UBOOT_DESC + 0x34, checksum)

    boot_region = bytearray(b"\xff" * BOOT_REGION_SIZE)
    boot_region[:BOOTSTRAP_SIZE] = bootstrap
    boot_region[UBOOT_OFFSET:] = partition

    (output_dir / "u-boot-fh8626v100-bootstrap.bin").write_bytes(bootstrap)
    (output_dir / "u-boot-fh8626v100-nor.bin").write_bytes(boot_region)

    print(f"old size:      {u32(flash, UBOOT_DESC + 0x18):#010x}")
    print(f"old aligned:   {old_aligned:#010x}")
    print(f"old JAMCRC:    {old_checksum:#010x} (verified)")
    print(
        "environment:   "
        f"{ENVIRONMENT_OFFSET:#010x}+{ENVIRONMENT_SIZE:#010x} erased"
    )


def main() -> None:
    """Parse command-line arguments and create release artifacts."""
    parser = argparse.ArgumentParser(
        description="Build FH8626V100 U-Boot NOR artifacts"
    )
    parser.add_argument("uboot", type=pathlib.Path, help="raw u-boot.bin")
    parser.add_argument("output_dir", type=pathlib.Path)
    parser.add_argument(
        "--flash-backup",
        type=pathlib.Path,
        help="verified 8 MiB NOR dump containing the board bootstrap",
    )
    args = parser.parse_args()

    image = args.uboot.read_bytes()
    flash = args.flash_backup.read_bytes() if args.flash_backup else None
    try:
        write_artifacts(image, args.output_dir, flash)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
