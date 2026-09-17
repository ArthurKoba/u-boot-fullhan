#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
"""Build the OpenIPC-native boot partition for ANJIA AJL33PQ0866."""

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
ENVIRONMENT_OFFSET = 0x40000
ENVIRONMENT_SIZE = 0x10000
BOOT_PARTITION_SIZE = 0x40000
KERNEL_OFFSET = 0x50000
KERNEL_SIZE = 0x200000
ROOTFS_OFFSET = 0x250000
ROOTFS_SIZE = 0x500000
ROOTFS_DATA_OFFSET = 0x750000
FLASH_SIZE = 0x800000
FIXED_UBOOT_JAMCRC = STOCK.FIXED_UBOOT_JAMCRC

DEFAULT_MANIFEST = (
    ROOT / "board" / "fullhan" / "fh8626v100" / "bootrom.json"
)
ARTIFACT_PREFIX = "u-boot-fh8626v100-anjia-ajl33pq0866"


def build_uboot_partition(image: bytes) -> bytes:
    """Pad U-Boot to the 192 KiB OpenIPC boot-partition payload contract."""
    if not image:
        raise ValueError("U-Boot image is empty")

    payload_limit = UBOOT_SLOT_SIZE - 4
    if len(image) > payload_limit:
        raise ValueError(
            f"U-Boot size {len(image):#x} exceeds OpenIPC payload limit "
            f"{payload_limit:#x}"
        )

    partition = bytearray(b"\xff" * UBOOT_SLOT_SIZE)
    partition[:len(image)] = image
    partition[-4:] = STOCK.crc32_fixup(
        bytes(partition[:-4]), FIXED_UBOOT_JAMCRC
    )
    if STOCK.jamcrc(partition) != FIXED_UBOOT_JAMCRC:
        raise ValueError("OpenIPC U-Boot JAMCRC verification failed")

    return bytes(partition)


def build_openipc_bootstrap(manifest: dict) -> bytes:
    """Move the ROM-visible U-Boot payload into OpenIPC's 256 KiB boot area."""
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

    offset = uboot.table_offset
    STOCK.put_u32(bootstrap, offset + 0x18, UBOOT_SLOT_SIZE)
    STOCK.put_u32(bootstrap, offset + 0x20, UBOOT_SLOT_SIZE)
    STOCK.put_u32(bootstrap, offset + 0x24, UBOOT_OFFSET)
    STOCK.put_u32(bootstrap, offset + 0x34, FIXED_UBOOT_JAMCRC)

    return bytes(bootstrap)


def build_boot_image(image: bytes, manifest: dict) -> tuple[bytes, bytes, bytes]:
    """Return bootstrap, padded U-Boot and the 256 KiB OpenIPC boot image."""
    bootstrap = build_openipc_bootstrap(manifest)
    partition = build_uboot_partition(image)
    boot = bootstrap + partition
    if len(boot) != BOOT_PARTITION_SIZE:
        raise ValueError("OpenIPC boot partition has an invalid size")
    validate_boot_image(boot)
    return bootstrap, partition, boot


def validate_boot_image(boot: bytes) -> None:
    """Validate OpenIPC layout and the ROM-visible U-Boot descriptor."""
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
    if uboot.raw_size != UBOOT_SLOT_SIZE or uboot.aligned_size != UBOOT_SLOT_SIZE:
        raise ValueError("OpenIPC U-Boot descriptor has the wrong size")
    if uboot.checksum != FIXED_UBOOT_JAMCRC:
        raise ValueError("OpenIPC U-Boot descriptor has the wrong JAMCRC")

    payload = boot[UBOOT_OFFSET:UBOOT_OFFSET + UBOOT_SLOT_SIZE]
    calculated = STOCK.jamcrc(payload)
    if calculated != uboot.checksum:
        raise ValueError(
            f"OpenIPC U-Boot JAMCRC mismatch: {calculated:#010x} != "
            f"{uboot.checksum:#010x}"
        )


def write_artifacts(image: bytes, output_dir: pathlib.Path, manifest: dict) -> None:
    """Write board-specific OpenIPC boot artifacts."""
    bootstrap, partition, boot = build_boot_image(image, manifest)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / f"{ARTIFACT_PREFIX}-bootstrap.bin").write_bytes(bootstrap)
    (output_dir / f"{ARTIFACT_PREFIX}-uboot.bin").write_bytes(partition)
    (output_dir / f"{ARTIFACT_PREFIX}.bin").write_bytes(boot)

    print(f"raw U-Boot:     {len(image):#010x}")
    print(f"U-Boot slot:    {len(partition):#010x}")
    print(f"boot partition: {len(boot):#010x}")
    print(f"environment:    {ENVIRONMENT_OFFSET:#010x}+{ENVIRONMENT_SIZE:#010x}")
    print(f"kernel:         {KERNEL_OFFSET:#010x}+{KERNEL_SIZE:#010x}")
    print(f"rootfs:         {ROOTFS_OFFSET:#010x}+{ROOTFS_SIZE:#010x}")
    print(f"rootfs_data:    {ROOTFS_DATA_OFFSET:#010x}+remainder")


def inspect_boot(path: pathlib.Path) -> None:
    """Validate and print the native OpenIPC layout contract."""
    boot = path.read_bytes()
    validate_boot_image(boot)
    descriptors = STOCK.parse_descriptors(boot)
    uboot = next(descriptor for descriptor in descriptors if descriptor.name == "uboot")
    print(f"boot-size={len(boot):#x}")
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
    """Build or inspect an OpenIPC-native FH8626 boot artifact."""
    parser = argparse.ArgumentParser(
        description="Build the OpenIPC-native AJL33PQ0866 boot partition"
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
        help="validate an already-built 256 KiB OpenIPC boot image",
    )
    args = parser.parse_args()

    try:
        if args.inspect:
            if args.output_dir is not None:
                parser.error("output_dir is not accepted with --inspect")
            inspect_boot(args.input)
            return

        if args.output_dir is None:
            parser.error("output_dir is required when building artifacts")
        manifest = json.loads(args.bootstrap_manifest.read_text(encoding="utf-8"))
        write_artifacts(args.input.read_bytes(), args.output_dir, manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
