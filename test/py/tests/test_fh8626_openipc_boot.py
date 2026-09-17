# SPDX-License-Identifier: GPL-2.0+
"""Tests for the OpenIPC-native FH8626 boot artifacts."""

import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "fh8626_openipc_boot", ROOT / "tools" / "fh8626_openipc_boot.py"
)
BOOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOOT)


class Fh8626OpenipcBootTest(unittest.TestCase):
    """Verify the OpenIPC 8 MiB NOR contract."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            BOOT.DEFAULT_MANIFEST.read_text(encoding="utf-8")
        )

    def test_partition_tracks_actual_payload(self):
        image = b"openipc-u-boot" * 101
        partition, aligned, checksum = BOOT.build_uboot_partition(image)

        self.assertEqual(len(partition), 0x30000)
        self.assertEqual(partition[:len(image)], image)
        self.assertEqual(aligned, BOOT.align_up(len(image), 0x100))
        self.assertEqual(
            partition[len(image):aligned],
            b"\xff" * (aligned - len(image)),
        )
        self.assertEqual(
            partition[aligned:], b"\xff" * (0x30000 - aligned)
        )
        self.assertEqual(BOOT.STOCK.jamcrc(partition[:aligned]), checksum)

    def test_bootstrap_moves_uboot_and_describes_actual_payload(self):
        image = b"native-u-boot" * 173
        partition, aligned, checksum = BOOT.build_uboot_partition(image)
        bootstrap = BOOT.build_openipc_bootstrap(
            self.manifest, len(image), aligned, checksum
        )
        descriptors = BOOT.STOCK.parse_descriptors(bootstrap)
        uboot = next(entry for entry in descriptors if entry.name == "uboot")

        self.assertEqual(uboot.flash_offset, 0x10000)
        self.assertEqual(uboot.raw_size, len(image))
        self.assertEqual(uboot.aligned_size, aligned)
        self.assertEqual(uboot.load_address, 0xA0800000)
        self.assertEqual(uboot.entry_address, 0xA0800000)
        self.assertEqual(uboot.checksum, checksum)
        self.assertEqual(
            BOOT.STOCK.jamcrc(partition[:uboot.aligned_size]),
            uboot.checksum,
        )

    def test_complete_boot_partition_is_256k(self):
        _, _, boot = BOOT.build_boot_image(b"u-boot" * 1000, self.manifest)

        self.assertEqual(len(boot), 0x40000)
        BOOT.validate_boot_image(boot)

    def test_openipc_nor_image_is_320k_with_erased_env(self):
        _, _, boot, nor = BOOT.build_nor_image(
            b"u-boot" * 1000, self.manifest
        )

        self.assertEqual(len(nor), 0x50000)
        self.assertEqual(nor[:0x40000], boot)
        self.assertEqual(nor[0x40000:], b"\xff" * 0x10000)
        BOOT.validate_nor_image(nor)

    def test_standard_openipc_8m_offsets(self):
        self.assertEqual(BOOT.ENVIRONMENT_OFFSET, 0x40000)
        self.assertEqual(BOOT.NOR_IMAGE_SIZE, 0x50000)
        self.assertEqual(BOOT.KERNEL_OFFSET, 0x50000)
        self.assertEqual(BOOT.KERNEL_SIZE, 0x200000)
        self.assertEqual(BOOT.ROOTFS_OFFSET, 0x250000)
        self.assertEqual(BOOT.ROOTFS_SIZE, 0x500000)
        self.assertEqual(BOOT.ROOTFS_DATA_OFFSET, 0x750000)
        self.assertEqual(BOOT.FLASH_SIZE, 0x800000)

    def test_rejects_dirty_environment_in_nor_image(self):
        _, _, _, nor = BOOT.build_nor_image(b"u-boot" * 1000, self.manifest)
        corrupt = bytearray(nor)
        corrupt[BOOT.ENVIRONMENT_OFFSET] = 0

        with self.assertRaisesRegex(ValueError, "environment sector"):
            BOOT.validate_nor_image(bytes(corrupt))

    def test_rejects_payload_larger_than_physical_slot(self):
        with self.assertRaisesRegex(ValueError, "exceeds OpenIPC slot"):
            BOOT.build_uboot_partition(b"x" * (BOOT.UBOOT_SLOT_SIZE + 1))

    def test_accepts_payload_exactly_filling_physical_slot(self):
        image = b"x" * BOOT.UBOOT_SLOT_SIZE
        partition, aligned, checksum = BOOT.build_uboot_partition(image)

        self.assertEqual(aligned, BOOT.UBOOT_SLOT_SIZE)
        self.assertEqual(partition, image)
        self.assertEqual(BOOT.STOCK.jamcrc(partition), checksum)


if __name__ == "__main__":
    unittest.main()
