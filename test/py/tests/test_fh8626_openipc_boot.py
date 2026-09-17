# SPDX-License-Identifier: GPL-2.0+
"""Tests for the OpenIPC-native FH8626 boot partition."""

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

    def test_partition_has_fixed_192k_envelope(self):
        image = b"openipc-u-boot" * 101
        partition = BOOT.build_uboot_partition(image)

        self.assertEqual(len(partition), 0x30000)
        self.assertEqual(partition[:len(image)], image)
        self.assertEqual(
            BOOT.STOCK.jamcrc(partition), BOOT.FIXED_UBOOT_JAMCRC
        )

    def test_bootstrap_moves_uboot_to_openipc_boot_partition(self):
        bootstrap = BOOT.build_openipc_bootstrap(self.manifest)
        descriptors = BOOT.STOCK.parse_descriptors(bootstrap)
        uboot = next(entry for entry in descriptors if entry.name == "uboot")

        self.assertEqual(uboot.flash_offset, 0x10000)
        self.assertEqual(uboot.raw_size, 0x30000)
        self.assertEqual(uboot.aligned_size, 0x30000)
        self.assertEqual(uboot.load_address, 0xA0800000)
        self.assertEqual(uboot.entry_address, 0xA0800000)
        self.assertEqual(uboot.checksum, BOOT.FIXED_UBOOT_JAMCRC)

    def test_complete_boot_partition_is_256k(self):
        _, _, boot = BOOT.build_boot_image(b"u-boot" * 1000, self.manifest)

        self.assertEqual(len(boot), 0x40000)
        BOOT.validate_boot_image(boot)

    def test_standard_openipc_8m_offsets(self):
        self.assertEqual(BOOT.ENVIRONMENT_OFFSET, 0x40000)
        self.assertEqual(BOOT.KERNEL_OFFSET, 0x50000)
        self.assertEqual(BOOT.KERNEL_SIZE, 0x200000)
        self.assertEqual(BOOT.ROOTFS_OFFSET, 0x250000)
        self.assertEqual(BOOT.ROOTFS_SIZE, 0x500000)
        self.assertEqual(BOOT.ROOTFS_DATA_OFFSET, 0x750000)
        self.assertEqual(BOOT.FLASH_SIZE, 0x800000)

    def test_rejects_oversized_uboot(self):
        with self.assertRaisesRegex(ValueError, "exceeds OpenIPC payload limit"):
            BOOT.build_uboot_partition(b"x" * (BOOT.UBOOT_SLOT_SIZE - 3))


if __name__ == "__main__":
    unittest.main()
