.. SPDX-License-Identifier: GPL-2.0+

Migrating AJL33PQ0866 to the native OpenIPC layout
==================================================

Status
------

This document describes the intended one-time transition from the factory
Fullhan NOR geometry to the standard OpenIPC 8 MiB NOR layout.  The underlying
FH8626V100 U-Boot port and the older stock-compatible replacement path are
hardware-proven.  The complete native-layout migration described here remains
a candidate until it has passed a cold boot on the physical camera.

Do not describe this procedure as hardware-accepted before that test.

Target layout
-------------

After migration the flash uses the normal OpenIPC 8 MiB geometry::

    0x000000  0x040000  boot
    0x040000  0x010000  env
    0x050000  0x200000  kernel
    0x250000  0x500000  rootfs
    0x750000  0x0b0000  rootfs_data

The 256 KiB ``boot`` partition contains the FH8626 board-specific split::

    0x000000  0x010000  Fullhan Boot ROM data container
    0x010000  0x030000  current U-Boot

The ROM-visible U-Boot load/entry address remains ``0xa0800000``.  Only its
SPI-NOR source offset changes, from the factory ``0x20000`` to ``0x10000``.
The persistent environment moves to the OpenIPC offset ``0x40000``.

Prerequisites
-------------

#. Keep an externally verified full 8 MiB factory dump.  Read it at least twice
   with an SPI programmer and compare the copies byte-for-byte.
#. Keep the programmer and a serial console available until native cold boot is
   proven.
#. Build the OpenIPC-native U-Boot and RAM recovery targets from the same
   reviewed revision.
#. Build the intended OpenIPC kernel and rootfs from reviewed revisions.
#. Verify that ``uImage.fh8626v100`` is no larger than ``0x200000`` bytes.
#. Verify that ``rootfs.squashfs.fh8626v100`` is no larger than ``0x500000``
   bytes.
#. Record host SHA-256 values for all four migration inputs.
#. Do not continue with unstable power.

The required files are::

    u-boot-fh8626v100-anjia-ajl33pq0866-ram.bin
    u-boot-fh8626v100-anjia-ajl33pq0866.bin
    uImage.fh8626v100
    rootfs.squashfs.fh8626v100

The board-specific U-Boot artifact must be exactly ``0x40000`` bytes.

Stage 1: enter RAM U-Boot
-------------------------

Interrupt the factory bootloader and load the non-persistent target at
``0xa3000000``::

    setenv serverip <tftp-server-ip>
    setenv ipaddr <temporary-camera-ip>
    tftpboot 0xa3000000 u-boot-fh8626v100-anjia-ajl33pq0866-ram.bin
    crc32 0xa3000000 ${filesize}
    go 0xa3000000

Compare the reported CRC with the host copy before ``go``.  The RAM target is
used because it does not execute from the flash-linked U-Boot region while the
NOR layout is being replaced.

Before any erase, verify at least::

    sf probe 0:0 50000000
    gpio status -a
    ping ${serverip}

A RAM-chainload failure, SPI failure or network failure is a stop condition.

Stage 2: write the OpenIPC kernel
---------------------------------

Load the kernel at ``0xa1000000``.  Confirm the received size is at most
``0x200000``::

    tftpboot 0xa1000000 uImage.fh8626v100
    crc32 0xa1000000 ${filesize}

Then erase the complete OpenIPC kernel partition, write the image, read it back
to an independent buffer and compare the exact transferred length::

    sf erase 0x50000 0x200000
    sf write 0xa1000000 0x50000 ${filesize}
    sf read 0xa1300000 0x50000 ${filesize}
    cmp.b 0xa1000000 0xa1300000 ${filesize}

Do not proceed if the comparison fails.

Stage 3: write the OpenIPC rootfs
---------------------------------

Load the rootfs and confirm it is at most ``0x500000`` bytes::

    tftpboot 0xa1000000 rootfs.squashfs.fh8626v100
    crc32 0xa1000000 ${filesize}

Write and verify it::

    sf erase 0x250000 0x500000
    sf write 0xa1000000 0x250000 ${filesize}
    sf read 0xa1a00000 0x250000 ${filesize}
    cmp.b 0xa1000000 0xa1a00000 ${filesize}

Prepare an empty persistent overlay area::

    sf erase 0x750000 0x0b0000

At this point the factory Linux filesystem layout has been intentionally
replaced.  Do not reset into the factory boot path.

Stage 4: install the native OpenIPC boot partition
--------------------------------------------------

Load the 256 KiB board-specific boot artifact and require the transfer size to
be exactly ``0x40000``::

    tftpboot 0xa1000000 u-boot-fh8626v100-anjia-ajl33pq0866.bin
    crc32 0xa1000000 0x40000

The destructive bootloader step is intentionally last.  Erase/write the full
OpenIPC ``boot`` partition and verify every byte::

    sf erase 0x00000 0x40000
    sf write 0xa1000000 0x00000 0x40000
    sf read 0xa1800000 0x00000 0x40000
    cmp.b 0xa1000000 0xa1800000 0x40000

Then erase the new OpenIPC environment sector so U-Boot starts from its
compiled OpenIPC defaults::

    sf erase 0x40000 0x10000

Do not reset unless the boot read-back comparison succeeded and the kernel and
rootfs comparisons from the previous stages also succeeded.

Stage 5: first native cold boot
-------------------------------

Reset the board::

    reset

Expected U-Boot properties are:

* prompt ``OpenIPC #``;
* U-Boot loaded by the Fullhan ROM container from NOR offset ``0x10000``;
* erased SPI environment detected and compiled defaults used;
* ``mtdparts`` equal to
  ``spi_flash:256k(boot),64k(env),2048k(kernel),5120k(rootfs),-(rootfs_data)``;
* ``bootcmd`` executes ``bootcmdnor``;
* kernel read from ``0x50000`` with a 2 MiB partition envelope;
* Linux root at ``/dev/mtdblock3``;
* usable ``ethaddr`` passed into the FH8626 Linux platform.

After Linux reaches userspace, verify the MTD map before making the environment
persistent.  Then the OpenIPC-side ``fw_printenv`` / ``fw_setenv`` flow may be
used normally.

Recovery
--------

Power loss after the factory layout has been overwritten can require external
SPI-NOR recovery.  The Fullhan mask ROM does not provide a general network
recovery path for this board.  Restore the verified full dump with the external
programmer if the generated Boot ROM data, relocated U-Boot or new firmware
cannot cold boot.

The factory layout is evidence and a recovery source after migration; it is not
the production architecture.
