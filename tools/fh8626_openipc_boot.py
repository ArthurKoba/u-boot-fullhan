#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
"""Build OpenIPC-native boot artifacts for ANJIA AJL33PQ0866."""

import argparse
import importlib.util
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
STOCK_SPEC = importlib.util.spec_from_file_location(
    "fh8626_bootchain", ROOT / "tools" / "fh8626_bootchain.py"
)
STOCK = importlib.util.module_from_spec(STOCK_SPEC)
STOCK_SPEC.loader.exec_module(STOCK)

BOOTSTRAP_SIZE = 0x10000
UBOOT_OFFSET = 0x10000
UBOOT_SLOT_SIZE = 0x30000
UBOOT_ALIGNMENT = 0x100
ENVIRONMENT_OFFSET = 0x40000
ENVIRONMENT_SIZE = 0x10000
BOOT_PARTITION_SIZE = 0x40000
KERNEL_OFFSET = 0x50000
NOR_IMAGE_SIZE = KERNEL_OFFSET
KERNEL_SIZE = 0x200000
ROOTFS_OFFSET = 0x250000
ROOTFS_SIZE = 0x500000
ROOTFS_DATA_OFFSET = 0x750000
FLASH_SIZE = 0x800000

DEFAULT_MANIFEST = (
    ROOT / "board" / "fullhan" / "fh8626v100" / "bootrom.json"
)
ARTIFACT_PREFIX = "u-boot-fh8626v100-anjia-ajl33pq0866"


def align_up(value: int, alignment: int) -> int:
    """Round *value* up to an integer power-of-two alignment."""
    if alignment <= 0 or alignment & (alignment - 1):
        raise ValueError("alignment must be a positive power of two")
    return (value + alignment - 1) & ~(alignment - 1)


def build_uboot_partition(image: bytes) -> tuple[bytes, int, int]:
    """Pad U-Boot to its 192 KiB physical slot and derive ROM metadata."""
    if not image:
        raise ValueError("U-Boot image is empty")
    if len(image) > UBOOT_SLOT_SIZE:
        raise ValueError(
            f"U-Boot size {len(image):#x} exceeds OpenIPC slot "
            f"{UBOOT_SLOT_SIZE:#x}"
        )

    aligned_size = align_up(len(image), UBOOT_ALIGNMENT)
    if aligned_size > UBOOT_SLOT_SIZE:
        raise ValueError(
            f"aligned U-Boot size {aligned_size:#x} exceeds OpenIPC slot "
            f"{UBOOT_SLOT_SIZE:#x}"
        )

    partition = bytearray(b"\xff" * UBOOT_SLOT_SIZE)
    partition[:len(image)] = image
    checksum = STOCK.jamcrc(partition[:aligned_size])
    return bytes(partition), aligned_size, checksum


def build_openipc_bootstrap(
    manifest: dict, raw_size: int, aligned_size: int, checksum: int
) -> bytes:
    """Move U-Boot into OpenIPC's boot area and describe the actual payload."""
    bootstrap = bytearray(STOCK.build_bootstrap(manifest))
    descriptors = STOCK.parse_descriptors(bootstrap)
    uboot = next(
        (descriptor for descriptor in descriptors if descriptor.name == "uboot"),
        None,
    )
    if uboot is None:
        raise ValueError("manifest has no U-Boot descriptor")
    if uboot.load_address != 0xA0800000 or uboot.entry_address != 0xA0800000:
        raise ValueError("unexpected U-Boot load/entry address in board manifest")
    if not 0 < raw_size <= aligned_size <= UBOOT_SLOT_SIZE:
        raise ValueError("invalid native U-Boot descriptor size")
    if aligned_size % UBOOT_ALIGNMENT:
        raise ValueError("native U-Boot descriptor is not 0x100-aligned")

    offset = uboot.table_offset
    STOCK.put_u32(bootstrap, offset + 0x18, raw_size)
    STOCK.put_u32(bootstrap, offset + 0x20, aligned_size)
    STOCK.put_u32(bootstrap, offset + 0x24, UBOOT_OFFSET)
    STOCK.put_u32(bootstrap, offset + 0x34, checksum)

    return bytes(bootstrap)


def build_boot_image(image: bytes, manifest: dict) -> tuple[bytes, bytes, bytes]:
    """Return bootstrap, padded U-Boot and the 256 KiB OpenIPC boot image."""
    partition, aligned_size, checksum = build_uboot_partition(image)
    bootstrap = build_openipc_bootstrap(
        manifest, len(image), aligned_size, checksum
    )
    boot = bootstrap + partition
    if len(boot) != BOOT_PARTITION_SIZE:
        raise ValueError("OpenIPC boot partition has an invalid size")
    validate_boot_image(boot)
    return bootstrap, partition, boot


def build_nor_image(image: bytes, manifest: dict) -> tuple[bytes, bytes, bytes, bytes]:
    """Return the 320 KiB OpenIPC NOR boot image including erased environment."""
    bootstrap, partition, boot = build_boot_image(image, manifest)
    nor = boot + b"\xff" * ENVIRONMENT_SIZE
    validate_nor_image(nor)
    return bootstrap, partition, boot, nor


def validate_boot_image(boot: bytes) -> None:
    """Validate the 256 KiB boot partition and ROM-visible descriptor."""
    if len(boot) != BOOT_PARTITION_SIZE:
        raise ValueError(
            f"boot image is {len(boot):#x}, expected {BOOT_PARTITION_SIZE:#x}"
        )

    descriptors = STOCK.parse_descriptors(boot)
    uboot = next(
        (descriptor for descriptor in descriptors if descriptor.name == "uboot"),
        None,
    )
    if uboot is None:
        raise ValueError("OpenIPC boot image has no U-Boot descriptor")
    if uboot.flash_offset != UBOOT_OFFSET:
        raise ValueError("OpenIPC U-Boot descriptor has the wrong flash offset")
    if not 0 < uboot.raw_size <= uboot.aligned_size <= UBOOT_SLOT_SIZE:
        raise ValueError("OpenIPC U-Boot descriptor has an invalid size")
    if uboot.aligned_size % UBOOT_ALIGNMENT:
        raise ValueError("OpenIPC U-Boot descriptor alignment is invalid")
    if uboot.load_address != 0xA0800000 or uboot.entry_address != 0xA0800000:
        raise ValueError("OpenIPC U-Boot descriptor has wrong load/entry address")

    payload = boot[UBOOT_OFFSET:UBOOT_OFFSET + UBOOT_SLOT_SIZE]
    if payload[uboot.raw_size:uboot.aligned_size] != \
            b"\xff" * (uboot.aligned_size - uboot.raw_size):
        raise ValueError("OpenIPC U-Boot alignment padding is not erased")
    if payload[uboot.aligned_size:] != \
            b"\xff" * (UBOOT_SLOT_SIZE - uboot.aligned_size):
        raise ValueError("OpenIPC U-Boot slot tail is not erased")

    calculated = STOCK.jamcrc(payload[:uboot.aligned_size])
    if calculated != uboot.checksum:
        raise ValueError(
            f"OpenIPC U-Boot JAMCRC mismatch: {calculated:#010x} != "
            f"{uboot.checksum:#010x}"
        )


def validate_nor_image(nor: bytes) -> None:
    """Validate the OpenIPC updater image: boot partition plus erased env."""
    if len(nor) != NOR_IMAGE_SIZE:
        raise ValueError(
            f"NOR image is {len(nor):#x}, expected {NOR_IMAGE_SIZE:#x}"
        )
    validate_boot_image(nor[:BOOT_PARTITION_SIZE])
    environment = nor[ENVIRONMENT_OFFSET:NOR_IMAGE_SIZE]
    if environment != b"\xff" * ENVIRONMENT_SIZE:
        raise ValueError("OpenIPC NOR image environment sector is not erased")


def write_artifacts(image: bytes, output_dir: pathlib.Path, manifest: dict) -> None:
    """Write board-specific OpenIPC boot/update artifacts."""
    bootstrap, partition, boot, nor = build_nor_image(image, manifest)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / f"{ARTIFACT_PREFIX}-bootstrap.bin").write_bytes(bootstrap)
    (output_dir / f"{ARTIFACT_PREFIX}-uboot.bin").write_bytes(partition)
    (output_dir / f"{ARTIFACT_PREFIX}-boot.bin").write_bytes(boot)
    (output_dir / f"{ARTIFACT_PREFIX}-nor.bin").write_bytes(nor)

    descriptor = next(
        entry for entry in STOCK.parse_descriptors(boot)
        if entry.name == "uboot"
    )
    print(f"raw U-Boot:     {descriptor.raw_size:#010x}")
    print(f"aligned U-Boot: {descriptor.aligned_size:#010x}")
    print(f"U-Boot JAMCRC:  {descriptor.checksum:#010x}")
    print(f"U-Boot slot:    {len(partition):#010x}")
    print(f"boot partition: {len(boot):#010x}")
    print(f"NOR boot image: {len(nor):#010x}")
    print(f"environment:    {ENVIRONMENT_OFFSET:#010x}+{ENVIRONMENT_SIZE:#010x}")
    print(f"kernel:         {KERNEL_OFFSET:#010x}+{KERNEL_SIZE:#010x}")
    print(f"rootfs:         {ROOTFS_OFFSET:#010x}+{ROOTFS_SIZE:#010x}")
    print(f"rootfs_data:    {ROOTFS_DATA_OFFSET:#010x}+remainder")


def inspect_image(path: pathlib.Path) -> None:
    """Validate and print an OpenIPC boot or NOR-update artifact."""
    image = path.read_bytes()
    if len(image) == BOOT_PARTITION_SIZE:
        validate_boot_image(image)
        boot = image
        kind = "boot"
    elif len(image) == NOR_IMAGE_SIZE:
        validate_nor_image(image)
        boot = image[:BOOT_PARTITION_SIZE]
        kind = "nor"
    else:
        raise ValueError(
            f"image is {len(image):#x}; expected {BOOT_PARTITION_SIZE:#x} "
            f"or {NOR_IMAGE_SIZE:#x}"
        )

    descriptors = STOCK.parse_descriptors(boot)
    uboot = next(descriptor for descriptor in descriptors if descriptor.name == "uboot")
    print(f"type={kind} size={len(image):#x}")
    print(
        "uboot "
        f"flash={uboot.flash_offset:#x} "
        f"size={uboot.raw_size:#x}/{uboot.aligned_size:#x} "
        f"load={uboot.load_address:#x} entry={uboot.entry_address:#x} "
        f"jamcrc={uboot.checksum:#010x} OK"
    )
    print(
        "layout "
        f"boot=0x0+{BOOT_PARTITION_SIZE:#x} "
        f"env={ENVIRONMENT_OFFSET:#x}+{ENVIRONMENT_SIZE:#x} "
        f"kernel={KERNEL_OFFSET:#x}+{KERNEL_SIZE:#x} "
        f"rootfs={ROOTFS_OFFSET:#x}+{ROOTFS_SIZE:#x} "
        f"rootfs_data={ROOTFS_DATA_OFFSET:#x}+remainder"
    )


def main() -> None:
    """Build or inspect an OpenIPC-native FH8626 artifact."""
    parser = argparse.ArgumentParser(
        description="Build OpenIPC-native AJL33PQ0866 boot artifacts"
    )
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("output_dir", type=pathlib.Path, nargs="?")
    parser.add_argument(
        "--bootstrap-manifest",
        type=pathlib.Path,
        default=DEFAULT_MANIFEST,
        help="recovered ANJIA Boot ROM data manifest",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="validate an already-built OpenIPC boot/NOR image",
    )
    args = parser.parse_args()

    try:
        if args.inspect:
            if args.output_dir is not None:
                parser.error("output_dir is not accepted with --inspect")
            inspect_image(args.input)
            return

        if args.output_dir is None:
            parser.error("output_dir is required when building artifacts")
        manifest = json.loads(args.bootstrap_manifest.read_text(encoding="utf-8"))
        write_artifacts(args.input.read_bytes(), args.output_dir, manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
