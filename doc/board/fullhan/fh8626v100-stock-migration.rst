.. SPDX-License-Identifier: GPL-2.0+

Migrating an FH8626V100 board from vendor U-Boot
================================================

Scope
-----

This procedure replaces only the 192 KiB U-Boot partition while retaining the
Fullhan bootstrap and persistent vendor environment.  It was hardware-validated
on an ANJIA AJL33PQ0866 with 64 MiB SDRAM and an 8 MiB MX25L6405D SPI NOR.
After a cold reset, the unchanged bootstrap loaded current U-Boot, the original
environment executed its GPIO and ``kload`` commands, and the complete stock
Linux firmware started successfully.

Other FH8626V100 cameras may use the same contract, but compatibility must not
be inferred from the SoC name alone.  Before persistent use, compare a full
dump with the expected geometry:

* bootstrap at ``0x00000``, size ``0x10000``;
* environment at ``0x10000``, size ``0x10000``;
* U-Boot at ``0x20000``, physical slot size ``0x30000``;
* U-Boot descriptor load and entry address ``0xa0800000``;
* descriptor raw size ``0x2bae4`` and aligned size ``0x2bb00``;
* descriptor JAMCRC ``0x251d4c31``.

DDR parameters, GPIO use, PHY wiring, RAM size and the remaining partition map
may differ between products.  Keep an external SPI-NOR programmer available
until a board has passed a cold boot.

Prerequisites
-------------

#. Read the complete flash at least twice with an external programmer and
   compare the reads byte-for-byte.  Store the matching dump and its SHA256
   outside the TFTP directory.
#. Build both targets from the same reviewed revision.
#. Put the RAM binary and padded partition in the TFTP root.
#. Record the SHA256 values from ``output/SHA256SUMS``.
#. Do not continue if power is unstable.

Build the production artifacts::

    CROSS_COMPILE=arm-linux-gnueabi- ./build.sh

Build the non-persistent trampoline::

    make O=build-ram CROSS_COMPILE=arm-linux-gnueabi- \
      fh8626v100_ram_defconfig
    make O=build-ram CROSS_COMPILE=arm-linux-gnueabi- -j8
    cp build-ram/u-boot.bin /tftp/root/u-boot-fh8626v100-ram.bin

Copy ``output/u-boot-fh8626v100-partition.bin`` to the same TFTP root.  The
partition must be exactly ``0x30000`` bytes.  Never substitute the raw
``u-boot-fh8626v100.bin`` file in the flash command.

Stage 1: enter the RAM target
-----------------------------

Stop vendor autoboot and configure network values appropriate for the local
network.  Load the RAM-linked target at ``0xa3000000``::

    setenv serverip 192.168.1.11
    setenv ipaddr 192.168.1.203
    tftpboot 0xa3000000 u-boot-fh8626v100-ram.bin
    crc32 0xa3000000 ${filesize}
    go 0xa3000000

Compare the CRC with the host copy before ``go``.  Do not load a flash-linked
binary at ``0xa0800000`` from the vendor U-Boot.  The vendor loader executes in
that region and will be overwritten during TFTP, normally hanging after the
first block.

The RAM target must report 64 MiB DRAM, the serial console and ``eth0``.  At
the ``FH8626V100 #`` prompt, perform non-persistent checks::

    help kload
    gpio 23 out 1
    sf probe 0:0 50000000
    kload
    iminfo 0xa1000000
    ping 192.168.1.1

Use a harmless GPIO appropriate for another board instead of GPIO 23.  The
image check must end in ``Verifying Checksum ... OK``.  Stop if SPI or Ethernet
fails; RAM-chainload success by itself is not sufficient.

An optional second backup can be taken through the RAM target::

    sf read 0xa1000000 0x000000 0x800000
    crc32 0xa1000000 0x800000
    tftpput 0xa1000000 0x800000 fh8626v100-pre-migration-full-8m.bin

Verify the received file size and host SHA256 before proceeding.  This backup
does not replace the externally programmed and verified recovery dump.

Stage 2: verify the immutable bootstrap and candidate
-----------------------------------------------------

Load the padded partition into a buffer that does not overlap either running
U-Boot::

    tftpboot 0xa1000000 u-boot-fh8626v100-partition.bin
    crc32 0xa1000000 0x30000

The current fixed-envelope packer produces partition CRC32 ``0x5189b2ff``.
Also compare the candidate against its host SHA256 and require TFTP to report
exactly ``196608 (30000 hex)`` bytes.

Read, but do not modify, the installed bootstrap::

    sf read 0xa1080000 0x00000 0x10000
    crc32 0xa1080000 0x10000

The validated AJL33PQ0866 bootstrap CRC32 is ``0x53241b1b``.  Another board
must use the CRC from its own verified dump and must pass the descriptor checks
listed above.

Stage 3: write only U-Boot
--------------------------

The following is the only destructive step.  The source buffer starts at
``0xa1000000`` and the independent read-back buffer at ``0xa1040000``::

    sf erase 0x20000 0x30000
    sf write 0xa1000000 0x20000 0x30000
    sf read 0xa1040000 0x20000 0x30000
    crc32 0xa1040000 0x30000
    cmp.b 0xa1000000 0xa1040000 0x30000

Do not reset unless the read-back CRC is ``0x5189b2ff`` and ``cmp.b`` reports
all 196608 bytes equal.  Offsets ``0x00000`` and ``0x10000`` must never be
erased or written by this procedure.

Optionally read the bootstrap once more after the write and confirm its CRC.
Then cold boot::

    reset

Expected cold-boot evidence
---------------------------

A successful migration shows all of the following without a RAM trampoline:

* Fullhan ROM selects NOR and initializes DDR;
* current U-Boot reports 64 MiB DRAM;
* ``Loading Environment from SPIFlash... OK``;
* SPI NOR and ``eth0`` are detected;
* the preserved vendor ``set_gpio`` commands execute through the compatibility
  syntax;
* ``kload`` reads the kernel and ``bootm`` verifies its checksum;
* Linux reaches userspace and the expected network address.

The installed vendor environment does not have to be rewritten for the first
boot.  Change and save environment variables only after the preserved boot
path has been proven.

Later U-Boot updates
--------------------

Once current U-Boot is installed, later updates do not need the RAM trampoline.
Load a newly generated padded partition at ``0xa1000000``, repeat the complete
CRC/write/read-back/compare gate, and continue to preserve bootstrap and
environment.  Every new build must still fit the ``0x2bb00`` ROM envelope.

Recovery
--------

Loss of power between erase and completed write can leave the board without a
valid U-Boot.  The mask ROM has no general TFTP recovery path for this board.
Restore the verified full 8 MiB dump with an external SPI-NOR programmer, then
verify the programmed chip byte-for-byte before reinstalling it.
