# SPDX-License-Identifier: GPL-2.0+
"""Tests for the FH8626V100 release-image packer."""

import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "fh8626_bootchain", ROOT / "tools" / "fh8626_bootchain.py"
)
BOOTCHAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOOTCHAIN)


class Fh8626BootchainTest(unittest.TestCase):
    """Exercise the fixed envelope and bootstrap descriptor contract."""

    @staticmethod
    def make_flash_backup() -> bytes:
        """Create a synthetic dump satisfying the validated ROM contract."""
        old_image = bytes(range(256)) * 3
        old_partition, old_aligned, old_checksum = \
            BOOTCHAIN.build_partition(old_image)
        flash = bytearray(b"\xff" * BOOTCHAIN.FLASH_SIZE)
        flash[:0x180] = b"\0" * 0x180
        flash[:4] = b"2BL*"
        BOOTCHAIN.put_u32(flash, 0x0c, 2)
        BOOTCHAIN.put_u32(flash, BOOTCHAIN.HEADER_SIZE_OFFSET, 0x180)
        flash[
            BOOTCHAIN.DESCRIPTOR_TABLE_OFFSET:
            BOOTCHAIN.DESCRIPTOR_TABLE_OFFSET + 16
        ] = b"param".ljust(16, b"\0")
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.DESCRIPTOR_TABLE_OFFSET + 0x20, 0x10
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.DESCRIPTOR_TABLE_OFFSET + 0x24, 0x1000
        )
        BOOTCHAIN.put_u32(
            flash,
            BOOTCHAIN.DESCRIPTOR_TABLE_OFFSET + 0x34,
            BOOTCHAIN.jamcrc(b"\0" * 0x10),
        )
        flash[0x1000:0x1010] = b"\0" * 0x10
        flash[
            BOOTCHAIN.UBOOT_DESC:BOOTCHAIN.UBOOT_DESC + 16
        ] = b"uboot".ljust(16, b"\0")
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x18, len(old_image)
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x14, 0x13579bdf
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x1c, 0x2468ace0
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x20, old_aligned
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x24, BOOTCHAIN.UBOOT_OFFSET
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x28, 0xa0800000
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x2c, 0xa0800000
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x34, old_checksum
        )
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x3c, 0x11223344
        )
        flash[
            BOOTCHAIN.UBOOT_OFFSET:
            BOOTCHAIN.UBOOT_OFFSET + old_aligned
        ] = old_partition[:old_aligned]
        return bytes(flash)

    def test_manifest_round_trip_is_lossless(self):
        """A dump reconstructed from its manifest is byte-identical."""
        flash = self.make_flash_backup()
        manifest = BOOTCHAIN.extract_manifest(flash)

        self.assertEqual(
            len(manifest["parameter_table"]["records"]), 1
        )
        self.assertEqual(manifest["parameter_table"]["active_records"], 0)
        self.assertEqual(
            BOOTCHAIN.build_bootstrap(manifest),
            flash[:BOOTCHAIN.BOOTSTRAP_SIZE],
        )

    def test_board_manifest_reproduces_validated_bootstrap(self):
        """The checked-in board data reconstructs the known 64 KiB image."""
        manifest_path = (
            ROOT / "board" / "fullhan" / "fh8626v100" / "bootrom.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bootstrap = BOOTCHAIN.build_bootstrap(manifest)

        self.assertEqual(
            hashlib.sha256(bootstrap).hexdigest(),
            "a45fdaa12f6a62db00abf24a04ce5745"
            "132d42194e60dc1c89d855bd38d9f3d8",
        )

    def test_parses_container_descriptors(self):
        """The documented 64-byte descriptor layout is machine-checked."""
        descriptors = BOOTCHAIN.parse_descriptors(self.make_flash_backup())

        self.assertEqual(
            [entry.name for entry in descriptors], ["param", "uboot"]
        )
        self.assertEqual(descriptors[1].table_offset, BOOTCHAIN.UBOOT_DESC)
        self.assertEqual(descriptors[1].flash_offset, BOOTCHAIN.UBOOT_OFFSET)
        self.assertEqual(
            BOOTCHAIN.descriptor_jamcrc(
                self.make_flash_backup(), descriptors[1]
            ),
            descriptors[1].checksum,
        )

    def test_partition_without_bootstrap(self):
        """The redistributable partition is always produced."""
        image = b"U-Boot" * 101
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            BOOTCHAIN.write_artifacts(image, output)
            partition = (
                output / "u-boot-fh8626v100-partition.bin"
            ).read_bytes()

            self.assertEqual(len(partition), BOOTCHAIN.UBOOT_SLOT_SIZE)
            self.assertEqual(partition[:len(image)], image)
            self.assertEqual(
                BOOTCHAIN.jamcrc(partition), BOOTCHAIN.FIXED_UBOOT_JAMCRC
            )
            self.assertFalse(
                (output / "u-boot-fh8626v100-nor.bin").exists()
            )

    def test_bootstrap_and_nor_image(self):
        """A validated dump produces a patched OpenIPC NOR asset."""
        image = b"mainline-u-boot" * 113
        expected_partition, aligned, checksum = \
            BOOTCHAIN.build_partition(image)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            BOOTCHAIN.write_artifacts(
                image, output, self.make_flash_backup()
            )
            bootstrap = (
                output / "u-boot-fh8626v100-bootstrap.bin"
            ).read_bytes()
            nor = (output / "u-boot-fh8626v100-nor.bin").read_bytes()

            self.assertEqual(len(bootstrap), BOOTCHAIN.BOOTSTRAP_SIZE)
            self.assertEqual(len(nor), BOOTCHAIN.BOOT_REGION_SIZE)
            self.assertEqual(
                BOOTCHAIN.u32(bootstrap, BOOTCHAIN.UBOOT_DESC + 0x18),
                BOOTCHAIN.UBOOT_SLOT_SIZE,
            )
            self.assertEqual(
                BOOTCHAIN.u32(bootstrap, BOOTCHAIN.UBOOT_DESC + 0x20),
                aligned,
            )
            self.assertEqual(
                BOOTCHAIN.u32(bootstrap, BOOTCHAIN.UBOOT_DESC + 0x34),
                checksum,
            )
            self.assertEqual(
                nor[BOOTCHAIN.ENVIRONMENT_OFFSET:BOOTCHAIN.UBOOT_OFFSET],
                b"\xff" * BOOTCHAIN.ENVIRONMENT_SIZE,
            )
            self.assertEqual(nor[BOOTCHAIN.UBOOT_OFFSET:], expected_partition)

    def test_bootstrap_is_stable_across_uboot_builds(self):
        """Future U-Boot updates do not require rewriting the bootstrap."""
        manifest_path = (
            ROOT / "board" / "fullhan" / "fh8626v100" / "bootrom.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        first = BOOTCHAIN.build_bootstrap(manifest, b"first build")
        second = BOOTCHAIN.build_bootstrap(manifest, b"different next build")

        self.assertEqual(first, second)
        self.assertEqual(
            BOOTCHAIN.u32(first, BOOTCHAIN.UBOOT_DESC + 0x18),
            BOOTCHAIN.UBOOT_SLOT_SIZE,
        )
        self.assertEqual(
            BOOTCHAIN.u32(first, BOOTCHAIN.UBOOT_DESC + 0x20),
            BOOTCHAIN.UBOOT_SLOT_SIZE,
        )
        self.assertEqual(
            BOOTCHAIN.u32(first, BOOTCHAIN.UBOOT_DESC + 0x34),
            BOOTCHAIN.FIXED_UBOOT_JAMCRC,
        )

    def test_fixed_envelopes_have_stable_jamcrc(self):
        """Different binaries share the ROM-visible checksum contract."""
        first, _, _ = BOOTCHAIN.build_partition(b"first build")
        second, _, _ = BOOTCHAIN.build_partition(b"different next build")

        self.assertNotEqual(first, second)
        self.assertEqual(
            BOOTCHAIN.jamcrc(first), BOOTCHAIN.FIXED_UBOOT_JAMCRC
        )
        self.assertEqual(
            BOOTCHAIN.jamcrc(second), BOOTCHAIN.FIXED_UBOOT_JAMCRC
        )

    def test_manifest_build_produces_complete_nor_image(self):
        """A source manifest can replace the private full-flash input."""
        flash = self.make_flash_backup()
        manifest = BOOTCHAIN.extract_manifest(flash)
        image = b"manifest-built-u-boot" * 101
        bootstrap = BOOTCHAIN.build_bootstrap(manifest, image)
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            BOOTCHAIN.write_artifacts(
                image, output, bootstrap=bootstrap
            )
            nor = (output / "u-boot-fh8626v100-nor.bin").read_bytes()

            self.assertEqual(len(nor), BOOTCHAIN.BOOT_REGION_SIZE)
            self.assertEqual(
                nor[:BOOTCHAIN.BOOTSTRAP_SIZE], bootstrap
            )

    def test_rejects_invalid_backup_checksum(self):
        """A corrupt input dump must never produce a boot image."""
        flash = bytearray(self.make_flash_backup())
        flash[BOOTCHAIN.UBOOT_OFFSET] ^= 1
        with self.assertRaisesRegex(ValueError, "JAMCRC mismatch"):
            BOOTCHAIN.validate_flash_backup(bytes(flash))

    def test_rejects_inconsistent_descriptor_counts(self):
        """Header group counts must cover the complete descriptor table."""
        flash = bytearray(self.make_flash_backup())
        BOOTCHAIN.put_u32(flash, 0x0c, 1)
        with self.assertRaisesRegex(ValueError, "descriptor counts"):
            BOOTCHAIN.parse_descriptors(bytes(flash))

    def test_rejects_oversized_uboot(self):
        """The immutable bootstrap slot limit is enforced."""
        accepted = b"x" * (BOOTCHAIN.UBOOT_SLOT_SIZE - 4)
        partition, _, _ = BOOTCHAIN.build_partition(accepted)
        self.assertEqual(partition[:len(accepted)], accepted)

        image = b"x" * (BOOTCHAIN.UBOOT_SLOT_SIZE - 3)
        with self.assertRaisesRegex(ValueError, "exceeds fixed-envelope"):
            BOOTCHAIN.build_partition(image)


if __name__ == "__main__":
    unittest.main()
