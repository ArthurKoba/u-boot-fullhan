#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
"""Create FH8626V100 U-Boot partition and NOR release artifacts."""

import argparse
import binascii
import dataclasses
import json
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
FIXED_UBOOT_JAMCRC = 0x251D4C31
HEADER_SIZE_OFFSET = 0x14
DESCRIPTOR_TABLE_OFFSET = 0x100
DESCRIPTOR_SIZE = 0x40
PARAM_RECORD_SIZE = 0x10
LEGACY_ENV_OFFSET = 0xe000


@dataclasses.dataclass(frozen=True)
class ImageDescriptor:
    """One image entry in the Fullhan Boot ROM container."""

    table_offset: int
    name: str
    selector: int
    reserved_14: int
    raw_size: int
    reserved_1c: int
    aligned_size: int
    flash_offset: int
    load_address: int
    entry_address: int
    attributes: int
    checksum: int
    subtype: int
    prefix_size: int


def u32(buf: bytes, offset: int) -> int:
    """Read a little-endian 32-bit integer from *buf*."""
    return struct.unpack_from("<I", buf, offset)[0]


def put_u32(buf: bytearray, offset: int, value: int) -> None:
    """Write a little-endian 32-bit integer to *buf*."""
    struct.pack_into("<I", buf, offset, value)


def jamcrc(data: bytes) -> int:
    """Return the JAMCRC variant used by the FH8626 bootstrap."""
    return binascii.crc32(data) ^ 0xffffffff


def crc32_fixup(prefix: bytes, target_jamcrc: int) -> bytes:
    """Return four bytes making ``jamcrc(prefix + fixup)`` equal *target*."""
    zero_suffix = b"\0" * 4
    baseline = jamcrc(prefix + zero_suffix)
    basis = [None] * 32
    basis_masks = [0] * 32

    for input_bit in range(32):
        suffix = bytearray(zero_suffix)
        suffix[input_bit // 8] = 1 << (input_bit % 8)
        vector = jamcrc(prefix + suffix) ^ baseline
        mask = 1 << input_bit
        for output_bit in range(31, -1, -1):
            if not vector & (1 << output_bit):
                continue
            if basis[output_bit] is None:
                basis[output_bit] = vector
                basis_masks[output_bit] = mask
                break
            vector ^= basis[output_bit]
            mask ^= basis_masks[output_bit]
        else:
            raise ValueError("CRC fixup matrix is singular")

    vector = baseline ^ target_jamcrc
    solution = 0
    for output_bit in range(31, -1, -1):
        if not vector & (1 << output_bit):
            continue
        if basis[output_bit] is None:
            raise ValueError("CRC target cannot be represented")
        vector ^= basis[output_bit]
        solution ^= basis_masks[output_bit]
    if vector:
        raise ValueError("CRC fixup failed")

    fixup = solution.to_bytes(4, "little")
    if jamcrc(prefix + fixup) != target_jamcrc:
        raise ValueError("CRC fixup verification failed")
    return fixup


def parse_descriptors(image: bytes) -> list[ImageDescriptor]:
    """Parse and validate the Fullhan container descriptor table."""
    if len(image) < DESCRIPTOR_TABLE_OFFSET:
        raise ValueError("image is too short for an FH8626 container")
    if image[:4] != b"2BL*":
        raise ValueError("invalid FH8626 bootstrap magic")

    header_size = u32(image, HEADER_SIZE_OFFSET)
    if (
        header_size < DESCRIPTOR_TABLE_OFFSET + DESCRIPTOR_SIZE
        or header_size > BOOTSTRAP_SIZE
        or header_size > len(image)
        or (header_size - DESCRIPTOR_TABLE_OFFSET) % DESCRIPTOR_SIZE
    ):
        raise ValueError(f"invalid descriptor table size {header_size:#x}")
    descriptor_count = (
        u32(image, 0x0c) + u32(image, 0x10)
    )
    table_descriptor_count = (
        header_size - DESCRIPTOR_TABLE_OFFSET
    ) // DESCRIPTOR_SIZE
    if descriptor_count != table_descriptor_count:
        raise ValueError("header descriptor counts do not match the table")

    descriptors = []
    for offset in range(
        DESCRIPTOR_TABLE_OFFSET, header_size, DESCRIPTOR_SIZE
    ):
        name_data = image[offset:offset + 16].split(b"\0", 1)[0]
        try:
            name = name_data.decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"non-ASCII descriptor name at {offset:#x}"
            ) from error
        if not name:
            raise ValueError(f"empty descriptor name at {offset:#x}")

        descriptors.append(
            ImageDescriptor(
                table_offset=offset,
                name=name,
                selector=u32(image, offset + 0x10),
                reserved_14=u32(image, offset + 0x14),
                raw_size=u32(image, offset + 0x18),
                reserved_1c=u32(image, offset + 0x1c),
                aligned_size=u32(image, offset + 0x20),
                flash_offset=u32(image, offset + 0x24),
                load_address=u32(image, offset + 0x28),
                entry_address=u32(image, offset + 0x2c),
                attributes=u32(image, offset + 0x30),
                checksum=u32(image, offset + 0x34),
                subtype=u32(image, offset + 0x38),
                prefix_size=u32(image, offset + 0x3c),
            )
        )

    return descriptors


def descriptor_jamcrc(image: bytes, descriptor: ImageDescriptor) -> int:
    """Calculate a descriptor payload checksum from a complete flash image."""
    start = descriptor.flash_offset
    end = start + descriptor.aligned_size
    if not descriptor.aligned_size or end > len(image):
        raise ValueError(f"{descriptor.name} payload is outside the image")
    return jamcrc(image[start:end])


def parse_param_records(
    image: bytes, descriptor: ImageDescriptor
) -> list[tuple[int, int, int, int]]:
    """Return active 16-byte records from a Fullhan ROM parameter table."""
    if descriptor.aligned_size % PARAM_RECORD_SIZE:
        raise ValueError("parameter table is not record-aligned")

    start = descriptor.flash_offset
    end = start + descriptor.aligned_size
    if end > len(image):
        raise ValueError("parameter table is outside the image")

    records = [
        struct.unpack_from("<4I", image, offset)
        for offset in range(start, end, PARAM_RECORD_SIZE)
    ]
    while records and not any(records[-1]):
        records.pop()
    return records


def inspect_container(image: bytes) -> None:
    """Print the confirmed structural properties of a Fullhan container."""
    descriptors = parse_descriptors(image)
    print(f"magic:          {image[:4].decode('ascii')}")
    print(f"product:        {u32(image, 0x04):#010x}")
    print(f"header size:    {u32(image, HEADER_SIZE_OFFSET):#06x}")
    print(f"descriptors:    {len(descriptors)}")

    for descriptor in descriptors:
        try:
            calculated = descriptor_jamcrc(image, descriptor)
            crc_state = "OK" if calculated == descriptor.checksum else "STALE"
        except ValueError:
            calculated = None
            crc_state = "UNAVAILABLE"
        checksum = (
            f"{descriptor.checksum:#010x}/{calculated:#010x} {crc_state}"
            if calculated is not None
            else f"{descriptor.checksum:#010x} {crc_state}"
        )
        print(
            f"{descriptor.table_offset:#05x} {descriptor.name:<8} "
            f"size={descriptor.raw_size:#x}/{descriptor.aligned_size:#x} "
            f"flash={descriptor.flash_offset:#x} "
            f"load={descriptor.load_address:#x} "
            f"entry={descriptor.entry_address:#x} "
            f"attributes={descriptor.attributes:#x} "
            f"subtype={descriptor.subtype:#x} "
            f"jamcrc={checksum}"
        )
        if descriptor.name == "param" or descriptor.name.startswith("DDR_"):
            records = parse_param_records(image, descriptor)
            operation_counts = {
                operation: sum(record[3] == operation for record in records)
                for operation in sorted({record[3] for record in records})
            }
            print(
                f"      records={len(records)} operations={operation_counts}"
            )


def hex32(value: int) -> str:
    """Format a manifest integer as an auditable 32-bit hexadecimal value."""
    return f"0x{value:08x}"


def manifest_value(value: int | str) -> int:
    """Read a JSON manifest integer in numeric or hexadecimal string form."""
    return int(value, 0) if isinstance(value, str) else value


def extract_manifest(image: bytes) -> dict:
    """Extract a structured bootstrap manifest from a flash dump."""
    descriptors = parse_descriptors(image)
    covered_header_words = {
        0x04, 0x08, 0x0c, 0x10, HEADER_SIZE_OFFSET, 0x18, 0x5c
    }
    metadata_layout = (
        (0x60, 0x20),
        (0x80, 0x20),
        (0xa0, 0x20),
        (0xc0, 0x20),
        (0xe0, 0x10),
    )
    metadata = []
    metadata_words = set()
    for offset, size in metadata_layout:
        data = image[offset:offset + size]
        metadata_words.update(range(offset, offset + size, 4))
        if data == b"\xff" * size:
            continue
        value = data.split(b"\0", 1)[0]
        try:
            text = value.decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError(f"non-ASCII metadata at {offset:#x}") from error
        entry = {"offset": hex(offset), "size": size, "value": text}
        if data != value.ljust(size, b"\0"):
            entry["raw_hex"] = data.hex()
        metadata.append(entry)

    reserved_words = {}
    for offset in range(0x1c, DESCRIPTOR_TABLE_OFFSET, 4):
        if offset in covered_header_words or offset in metadata_words:
            continue
        value = u32(image, offset)
        if value != 0xffffffff:
            reserved_words[hex(offset)] = hex32(value)

    manifest_descriptors = []
    for descriptor in descriptors:
        descriptor_entry = {
            "name": descriptor.name,
            "selector": hex32(descriptor.selector),
            "reserved_14": hex32(descriptor.reserved_14),
            "raw_size": hex32(descriptor.raw_size),
            "reserved_1c": hex32(descriptor.reserved_1c),
            "aligned_size": hex32(descriptor.aligned_size),
            "flash_offset": hex32(descriptor.flash_offset),
            "load_address": hex32(descriptor.load_address),
            "entry_address": hex32(descriptor.entry_address),
            "attributes": hex32(descriptor.attributes),
            "checksum": hex32(descriptor.checksum),
            "subtype": hex32(descriptor.subtype),
            "prefix_size": hex32(descriptor.prefix_size),
        }
        name_bytes = image[
            descriptor.table_offset:descriptor.table_offset + 16
        ]
        canonical_name = descriptor.name.encode("ascii").ljust(16, b"\0")
        if name_bytes != canonical_name:
            descriptor_entry["name_raw_hex"] = name_bytes.hex()
        manifest_descriptors.append(descriptor_entry)

    parameter = next(
        (descriptor for descriptor in descriptors if descriptor.name == "param"),
        None,
    )
    if parameter is None:
        raise ValueError("FH8626 param descriptor is missing")
    parameter_start = parameter.flash_offset
    parameter_end = parameter_start + parameter.aligned_size
    records = [
        struct.unpack_from("<4I", image, offset)
        for offset in range(parameter_start, parameter_end, PARAM_RECORD_SIZE)
    ]
    active_records = len(records)
    while active_records and not any(records[active_records - 1]):
        active_records -= 1

    legacy = image[LEGACY_ENV_OFFSET:BOOTSTRAP_SIZE]
    legacy_manifest = None
    if legacy[:4] != b"\xff" * 4:
        terminator = legacy.find(b"\0\0", 4)
        if terminator < 0:
            raise ValueError("legacy environment has no terminator")
        variables = legacy[4:terminator].split(b"\0")
        try:
            variable_text = [entry.decode("ascii") for entry in variables]
        except UnicodeDecodeError as error:
            raise ValueError("legacy environment is not ASCII") from error
        legacy_manifest = {
            "unknown_tag": hex32(u32(legacy, 0)),
            "variables": variable_text,
        }
        trailing = legacy[terminator + 2:]
        if trailing != b"\xff" * len(trailing):
            legacy_manifest["trailing_hex"] = trailing.hex()

    return {
        "spdx": "GPL-2.0+",
        "format_version": 2,
        "header": {
            "product_id": hex32(u32(image, 0x04)),
            "platform_selector": hex32(u32(image, 0x08)),
            "load_descriptor_count": u32(image, 0x0c),
            "preload_descriptor_count": u32(image, 0x10),
            "size": hex32(u32(image, HEADER_SIZE_OFFSET)),
            "marker": hex32(u32(image, 0x18)),
            "board_word_5c": hex32(u32(image, 0x5c)),
            "metadata": metadata,
            "reserved_words": reserved_words,
        },
        "descriptors": manifest_descriptors,
        "parameter_table": {
            "active_records": active_records,
            "records": [
                " ".join(f"{word:08x}" for word in record)
                for record in records
            ],
        },
        "legacy_environment": legacy_manifest,
    }


def build_bootstrap(manifest: dict, uboot_image: bytes | None = None) -> bytes:
    """Build a 64 KiB bootstrap from a structured board manifest."""
    if manifest.get("format_version") != 2:
        raise ValueError("unsupported bootstrap manifest version")

    header = manifest["header"]
    bootstrap = bytearray(b"\xff" * BOOTSTRAP_SIZE)
    bootstrap[:4] = b"2BL*"
    put_u32(bootstrap, 0x04, manifest_value(header["product_id"]))
    put_u32(
        bootstrap, 0x08, manifest_value(header["platform_selector"])
    )
    put_u32(bootstrap, 0x0c, header["load_descriptor_count"])
    put_u32(bootstrap, 0x10, header["preload_descriptor_count"])
    put_u32(
        bootstrap, HEADER_SIZE_OFFSET, manifest_value(header["size"])
    )
    put_u32(bootstrap, 0x18, manifest_value(header["marker"]))
    put_u32(bootstrap, 0x5c, manifest_value(header["board_word_5c"]))

    for entry in header["metadata"]:
        offset = manifest_value(entry["offset"])
        size = entry["size"]
        if "raw_hex" in entry:
            value = bytes.fromhex(entry["raw_hex"])
            if len(value) != size:
                raise ValueError(f"metadata at {offset:#x} has wrong size")
        else:
            text = entry["value"].encode("ascii")
            if len(text) >= size:
                raise ValueError(f"metadata at {offset:#x} is too long")
            value = text.ljust(size, b"\0")
        bootstrap[offset:offset + size] = value
    for offset, value in header["reserved_words"].items():
        put_u32(bootstrap, manifest_value(offset), manifest_value(value))

    descriptors = manifest["descriptors"]
    expected_header_size = DESCRIPTOR_TABLE_OFFSET + (
        len(descriptors) * DESCRIPTOR_SIZE
    )
    if manifest_value(header["size"]) != expected_header_size:
        raise ValueError("manifest descriptor count does not match header size")
    descriptor_count = (
        header["load_descriptor_count"]
        + header["preload_descriptor_count"]
    )
    if descriptor_count != len(descriptors):
        raise ValueError("header descriptor counts do not match the table")

    uboot_aligned = None
    uboot_checksum = None
    if uboot_image is not None:
        _, uboot_aligned, uboot_checksum = build_partition(
            uboot_image
        )

    parameter_descriptor = None
    for index, entry in enumerate(descriptors):
        offset = DESCRIPTOR_TABLE_OFFSET + index * DESCRIPTOR_SIZE
        descriptor = bytearray(DESCRIPTOR_SIZE)
        name = entry["name"].encode("ascii")
        if not name or len(name) >= 16:
            raise ValueError(f"invalid descriptor name {entry['name']!r}")
        if "name_raw_hex" in entry:
            name_data = bytes.fromhex(entry["name_raw_hex"])
            if len(name_data) != 16 or not name_data.startswith(name + b"\0"):
                raise ValueError(f"invalid raw descriptor name {entry['name']!r}")
            descriptor[:16] = name_data
        else:
            descriptor[:16] = name.ljust(16, b"\0")

        values = {
            0x10: manifest_value(entry["selector"]),
            0x14: manifest_value(entry["reserved_14"]),
            0x18: manifest_value(entry["raw_size"]),
            0x1c: manifest_value(entry["reserved_1c"]),
            0x20: manifest_value(entry["aligned_size"]),
            0x24: manifest_value(entry["flash_offset"]),
            0x28: manifest_value(entry["load_address"]),
            0x2c: manifest_value(entry["entry_address"]),
            0x30: manifest_value(entry["attributes"]),
            0x34: manifest_value(entry["checksum"]),
            0x38: manifest_value(entry["subtype"]),
            0x3c: manifest_value(entry["prefix_size"]),
        }
        if entry["name"] == "uboot" and uboot_image is not None:
            values[0x18] = UBOOT_SLOT_SIZE
            values[0x20] = uboot_aligned
            values[0x34] = uboot_checksum
        for field_offset, value in values.items():
            put_u32(descriptor, field_offset, value)
        bootstrap[offset:offset + DESCRIPTOR_SIZE] = descriptor

        if entry["name"] == "param":
            parameter_descriptor = entry

    if parameter_descriptor is None:
        raise ValueError("manifest has no param descriptor")
    parameter_offset = manifest_value(parameter_descriptor["flash_offset"])
    parameter_size = manifest_value(parameter_descriptor["aligned_size"])
    if parameter_offset + parameter_size > BOOTSTRAP_SIZE:
        raise ValueError("parameter table exceeds the bootstrap")
    parameter_data = bytearray(parameter_size)
    parameter_table = manifest["parameter_table"]
    records = parameter_table["records"]
    expected_records = parameter_size // PARAM_RECORD_SIZE
    if len(records) != expected_records:
        raise ValueError(
            "parameter record count does not match the descriptor size"
        )
    active_records = parameter_table["active_records"]
    if not 0 <= active_records <= len(records):
        raise ValueError("invalid active parameter record count")
    if any(any(int(word, 16) for word in record.split())
           for record in records[active_records:]):
        raise ValueError("parameter padding contains an active record")
    for index, record in enumerate(records):
        words = [int(word, 16) for word in record.split()]
        if len(words) != 4:
            raise ValueError(f"invalid parameter record {index}")
        struct.pack_into("<4I", parameter_data, index * PARAM_RECORD_SIZE, *words)
    calculated = jamcrc(parameter_data)
    expected = manifest_value(parameter_descriptor["checksum"])
    if calculated != expected:
        raise ValueError(
            f"parameter JAMCRC mismatch: {calculated:#010x} != "
            f"{expected:#010x}"
        )
    bootstrap[
        parameter_offset:parameter_offset + parameter_size
    ] = parameter_data

    legacy = manifest.get("legacy_environment")
    if legacy is not None:
        put_u32(
            bootstrap,
            LEGACY_ENV_OFFSET,
            manifest_value(legacy["unknown_tag"]),
        )
        data = b"\0".join(
            variable.encode("ascii") for variable in legacy["variables"]
        ) + b"\0\0"
        end = LEGACY_ENV_OFFSET + 4 + len(data)
        if end > BOOTSTRAP_SIZE:
            raise ValueError("legacy environment exceeds the bootstrap")
        bootstrap[LEGACY_ENV_OFFSET + 4:end] = data
        if "trailing_hex" in legacy:
            trailing = bytes.fromhex(legacy["trailing_hex"])
            if end + len(trailing) != BOOTSTRAP_SIZE:
                raise ValueError("legacy trailing data has wrong size")
            bootstrap[end:] = trailing

    return bytes(bootstrap)


def build_partition(image: bytes) -> tuple[bytes, int, int]:
    """Return a fixed-envelope U-Boot partition and stable ROM contract."""
    if not image:
        raise ValueError("U-Boot image is empty")

    payload_limit = UBOOT_SLOT_SIZE - 4
    if len(image) > payload_limit:
        raise ValueError(
            f"U-Boot size {len(image):#x} exceeds fixed-envelope payload "
            f"limit {payload_limit:#x}"
        )

    partition = bytearray(b"\xff" * UBOOT_SLOT_SIZE)
    partition[:len(image)] = image
    partition[-4:] = crc32_fixup(
        bytes(partition[:-4]), FIXED_UBOOT_JAMCRC
    )
    if jamcrc(partition) != FIXED_UBOOT_JAMCRC:
        raise ValueError("fixed-envelope JAMCRC verification failed")
    return bytes(partition), UBOOT_SLOT_SIZE, FIXED_UBOOT_JAMCRC


def validate_flash_backup(flash: bytes) -> tuple[int, int]:
    """Validate an 8 MiB dump and return its U-Boot geometry."""
    if len(flash) != FLASH_SIZE:
        raise ValueError(
            f"flash backup is {len(flash):#x}, expected {FLASH_SIZE:#x}"
        )
    descriptors = parse_descriptors(flash)
    uboot = next(
        (descriptor for descriptor in descriptors if descriptor.name == "uboot"),
        None,
    )
    if uboot is None or uboot.table_offset != UBOOT_DESC:
        raise ValueError("U-Boot descriptor not found at 0x140")
    if uboot.flash_offset != UBOOT_OFFSET:
        raise ValueError("unexpected stock U-Boot flash offset")
    if uboot.load_address != 0xa0800000:
        raise ValueError("unexpected stock U-Boot load address")
    if uboot.entry_address != 0xa0800000:
        raise ValueError("unexpected stock U-Boot entry address")

    old_aligned = uboot.aligned_size
    if not old_aligned or old_aligned > UBOOT_SLOT_SIZE:
        raise ValueError("invalid U-Boot size in bootstrap descriptor")

    old_checksum = uboot.checksum
    calculated = descriptor_jamcrc(flash, uboot)
    if calculated != old_checksum:
        raise ValueError(
            f"stock JAMCRC mismatch: descriptor {old_checksum:#010x}, "
            f"calculated {calculated:#010x}"
        )

    return old_aligned, old_checksum


def write_artifacts(
    image: bytes,
    output_dir: pathlib.Path,
    flash: bytes | None = None,
    bootstrap: bytes | None = None,
) -> None:
    """Write the U-Boot partition and optional complete boot-region image."""
    if flash is not None and bootstrap is not None:
        raise ValueError("supply a flash backup or a bootstrap, not both")

    partition, aligned, checksum = build_partition(image)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "u-boot-fh8626v100-partition.bin").write_bytes(partition)

    print(f"binary size:   {len(image):#010x}")
    print(f"envelope size: {aligned:#010x}")
    print(f"fixed JAMCRC:  {checksum:#010x}")
    print(f"payload spare: {UBOOT_SLOT_SIZE - 4 - len(image):#010x}")

    if flash is None and bootstrap is None:
        print("bootstrap:     not supplied; skipping full NOR image")
        return

    if flash is not None:
        old_aligned, old_checksum = validate_flash_backup(flash)
        bootstrap_data = bytearray(flash[:BOOTSTRAP_SIZE])
        put_u32(bootstrap_data, UBOOT_DESC + 0x18, UBOOT_SLOT_SIZE)
        put_u32(bootstrap_data, UBOOT_DESC + 0x20, aligned)
        put_u32(bootstrap_data, UBOOT_DESC + 0x34, checksum)
        print(f"old size:      {u32(flash, UBOOT_DESC + 0x18):#010x}")
        print(f"old aligned:   {old_aligned:#010x}")
        print(f"old JAMCRC:    {old_checksum:#010x} (verified)")
    else:
        if len(bootstrap) != BOOTSTRAP_SIZE:
            raise ValueError("generated bootstrap is not 64 KiB")
        bootstrap_data = bytearray(bootstrap)

    boot_region = bytearray(b"\xff" * BOOT_REGION_SIZE)
    boot_region[:BOOTSTRAP_SIZE] = bootstrap_data
    boot_region[UBOOT_OFFSET:] = partition

    (output_dir / "u-boot-fh8626v100-bootstrap.bin").write_bytes(
        bootstrap_data
    )
    (output_dir / "u-boot-fh8626v100-nor.bin").write_bytes(boot_region)

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
    parser.add_argument("output_dir", type=pathlib.Path, nargs="?")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--flash-backup",
        type=pathlib.Path,
        help="verified 8 MiB NOR dump containing the board bootstrap",
    )
    source.add_argument(
        "--bootstrap-manifest",
        type=pathlib.Path,
        help="JSON board manifest used to generate the bootstrap",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--extract-manifest",
        type=pathlib.Path,
        metavar="OUTPUT_JSON",
        help="extract a structured bootstrap manifest from the input dump",
    )
    action.add_argument(
        "--inspect",
        action="store_true",
        help="inspect the container supplied as the uboot argument",
    )
    args = parser.parse_args()

    image = args.uboot.read_bytes()
    if args.inspect:
        try:
            inspect_container(image)
        except ValueError as error:
            parser.error(str(error))
        return

    if args.extract_manifest:
        if args.output_dir is not None:
            parser.error("output_dir is not accepted with --extract-manifest")
        try:
            validate_flash_backup(image)
            manifest = extract_manifest(image)
        except ValueError as error:
            parser.error(str(error))
        args.extract_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.extract_manifest.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return

    if args.output_dir is None:
        parser.error("output_dir is required when building artifacts")

    flash = args.flash_backup.read_bytes() if args.flash_backup else None
    try:
        bootstrap = None
        if args.bootstrap_manifest:
            manifest = json.loads(
                args.bootstrap_manifest.read_text(encoding="utf-8")
            )
            bootstrap = build_bootstrap(manifest, image)
        write_artifacts(image, args.output_dir, flash, bootstrap)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
