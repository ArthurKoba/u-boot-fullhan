# SPDX-License-Identifier: GPL-2.0+
"""Tests for the FH8626V100 release-image packer."""

import importlib.util
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
    """Exercise partition padding and bootstrap descriptor updates."""

    @staticmethod
    def make_flash_backup() -> bytes:
        """Create a synthetic dump satisfying the validated ROM contract."""
        old_image = bytes(range(256)) * 3
        old_partition, old_aligned, old_checksum = \
            BOOTCHAIN.build_partition(old_image)
        flash = bytearray(b"\xff" * BOOTCHAIN.FLASH_SIZE)
        flash[:4] = b"2BL*"
        flash[
            BOOTCHAIN.UBOOT_DESC:BOOTCHAIN.UBOOT_DESC + 16
        ] = b"uboot".ljust(16, b"\0")
        BOOTCHAIN.put_u32(
            flash, BOOTCHAIN.UBOOT_DESC + 0x18, len(old_image)
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
        flash[
            BOOTCHAIN.UBOOT_OFFSET:
            BOOTCHAIN.UBOOT_OFFSET + old_aligned
        ] = old_partition[:old_aligned]
        return bytes(flash)

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
                len(image),
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

    def test_rejects_invalid_backup_checksum(self):
        """A corrupt input dump must never produce a boot image."""
        flash = bytearray(self.make_flash_backup())
        flash[BOOTCHAIN.UBOOT_OFFSET] ^= 1
        with self.assertRaisesRegex(ValueError, "JAMCRC mismatch"):
            BOOTCHAIN.validate_flash_backup(bytes(flash))

    def test_rejects_oversized_uboot(self):
        """The immutable bootstrap slot limit is enforced."""
        image = b"x" * (BOOTCHAIN.UBOOT_SLOT_SIZE + 1)
        with self.assertRaisesRegex(ValueError, "exceeds slot"):
            BOOTCHAIN.build_partition(image)


if __name__ == "__main__":
    unittest.main()
