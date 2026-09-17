.. SPDX-License-Identifier: GPL-2.0+

FH8626V100 integration history and artifact policy
===================================================

Purpose
-------

This file records the durable engineering history of the FH8626V100 port as
validated on ANJIA AJL33PQ0866.  It is not a substitute for Git history and it
is not an authority for current OpenIPC rules.  Before contribution, re-check
the live upstream sources linked from the main README and the destination
repository's own contribution instructions.

Repository artifact policy
--------------------------

The source repository does **not** store generated firmware or U-Boot binaries.
Generated artifacts are build outputs only.

The repository keeps:

* U-Boot source changes;
* defconfigs and device-tree/board source;
* auditable Boot-ROM reconstruction data such as ``bootrom.json``;
* packers, validators and unit tests;
* build scripts and documentation;
* hashes/provenance references where an external binary or hardware dump must
  be identified.

The repository does not keep generated ``*.bin``, ``*.img``, ``*.elf`` or
other release images.  The top-level ``.gitignore`` excludes those formats and
also excludes ``/output/`` and build directories.

When binaries are required for hardware testing or release they should live in
one of these places, depending on the workflow:

* the local ignored ``output/`` directory for an active build/test session;
* a dedicated release/artifact store;
* a separate evidence/binary storage location when long-term retention is
  required.

Do not commit a generated binary merely to make a test, migration procedure or
CI job convenient.  Tests should reconstruct or validate artifacts from source
where practical.  Documentation should name the expected artifact and record
hash/provenance when needed, not embed the artifact in Git.

2026-09-02 -- initial FH8626V100 RAM bring-up
---------------------------------------------

The first porting step added a non-persistent ARM1176 RAM target.  It reused the
already-initialized Fullhan clock/SDRAM state and established modern U-Boot
serial, timer, reset and legacy ATAG boot support without writing SPI NOR.

2026-09-02/03 -- modern production port
---------------------------------------

The port was expanded from RAM bring-up into a flash-capable current-U-Boot
implementation with:

* FH8626V100 architecture/board support;
* DesignWare APB UART, timer, GPIO and SPI integration;
* Fullhan DesignWare Ethernet/RMII glue;
* legacy Linux 4.9 machine-ID/ATAG handoff;
* bounded DesignWare SPI transfers needed for reliable large NOR reads;
* OpenIPC-facing environment and network recovery functionality.

This work replaced Fullhan's old proprietary U-Boot implementation with a
modern open-source implementation while preserving the hardware contracts
needed to boot the board.

2026-09-03 -- Boot-ROM container reconstruction
-----------------------------------------------

The board-specific 64 KiB Fullhan ROM data container was reconstructed into an
auditable structured manifest and tooling.  The repository stores the recovered
board data and reconstruction logic, not a copied vendor U-Boot executable.

This established a reproducible description of the ROM-visible U-Boot payload,
DDR/board records and checksum contract.

2026-09-04 -- stock-compatible hardware acceptance
--------------------------------------------------

A stock-compatible migration path was validated on physical AJL33PQ0866
hardware.  That path retained the factory layout:

* container at ``0x00000``;
* environment at ``0x10000``;
* U-Boot at ``0x20000``;
* kernel starting at ``0x50000``.

The replacement U-Boot passed cold boot, SPI NOR reads, Ethernet/TFTP, GPIO,
legacy Linux handoff and boot of OpenIPC.  It also booted the installed factory
firmware, which made this state a useful recovery/reference baseline.

The preserved baseline is:

``fh8626v100-stock-compatible@49fe46e9ddb786e232d1359f9cee68c914a3a8db``

2026-09-17 -- OpenIPC-native architecture
-----------------------------------------

The project stopped treating the factory Fullhan partition map as the product
architecture.  The target was changed to the normal OpenIPC 8 MiB NOR layout:

``256k(boot),64k(env),2048k(kernel),5120k(rootfs),-(rootfs_data)``

The FH8626-specific first stage is now contained inside the normal OpenIPC
``boot`` partition:

* ``0x00000..0x0ffff`` -- board-specific Fullhan ROM/DDR data;
* ``0x10000..0x3ffff`` -- 192 KiB U-Boot physical slot;
* ``0x40000..0x4ffff`` -- OpenIPC environment;
* ``0x50000`` -- kernel;
* ``0x250000`` -- rootfs;
* ``0x750000`` -- rootfs_data.

Production was detached from the factory environment.  Factory ``kload``,
legacy GPIO command syntax and related compatibility behavior are retained only
in the RAM migration/recovery configuration.

The production environment was aligned with OpenIPC NOR conventions, including
``kernaddr``/``kernsize``, ``rootaddr``/``rootsize``, ``cmdnor``,
``bootcmdnor``, ``updatetool``, ``ubnor``/``ubwrite``, ``uknor``/``ukwrite``
and ``urnor``/``urwrite``.

The production updater artifact is generated as a 320 KiB NOR image covering
``boot + erased env`` through offset ``0x50000``.  It is generated into the
ignored build output directory and is not committed to Git.

The native packer no longer forces the factory U-Boot size/JAMCRC.  It records
the actual raw U-Boot size, aligns it to ``0x100`` and calculates the ROM
checksum from the resulting payload while keeping the remainder of the 192 KiB
physical slot erased.

The latest source/build candidate reached:

* raw U-Boot: ``0x2ef20``;
* aligned ROM payload: ``0x2f000``;
* U-Boot slot: ``0x30000``;
* generated NOR updater span: ``0x50000``;
* dynamic JAMCRC: ``0x0c6d419b`` for that exact build.

The source/build implementation is the current ``fh8626v100-mainline`` line.
The stock-compatible state remains separately preserved for recovery.

Remaining acceptance boundary
-----------------------------

The OpenIPC-native implementation is not yet hardware-accepted.  Before it can
replace the recovery baseline as a proven installed state:

#. build the final FH8626 OpenIPC kernel and confirm the resulting ``uImage``
   fits the standard 2 MiB partition;
#. perform the documented one-time full-layout migration with a verified full
   flash backup and external SPI recovery available;
#. cold-boot the physical AJL33PQ0866;
#. verify the new MTD map, persistent environment, kernel/rootfs boot and
   network/MAC behavior.

Only then should the native state be promoted from source/build evidence to
``HARDWARE_PASS`` and curated into the final OpenIPC contribution series.
