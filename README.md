# OpenIPC U-Boot for Fullhan FH8626V100

This repository carries a current-upstream U-Boot port for the Fullhan
FH8626V100 camera SoC. It supports UART, 64 MiB DRAM, GPIO, SPI NOR and RMII
Ethernet, and provides an OpenIPC-compatible default environment.

The production port is hardware-tested on an ANJIA AJL33PQ0866 camera with an
8 MiB MX25L6405D NOR flash. It has replaced the vendor U-Boot while retaining
the original Fullhan bootstrap and environment, then cold-booted the complete
installed stock firmware. A non-persistent RAM target remains available for
bring-up and recovery.

## What this port changes

Compared with upstream U-Boot, this repository adds:

- FH8626V100 SoC and board initialization;
- DesignWare APB UART, timer, GPIO and SPI integration for this SoC;
- FH8626V100 DesignWare Ethernet/RMII support;
- legacy ATAG and machine-ID boot required by the available Linux 4.9 port;
- a bounded SPI FIFO path that avoids receive overruns on 3 MiB reads;
- an OpenIPC raw-NOR layout, environment and reproducible boot-chain packer;
- RAM and stock-bootstrap-compatible flash configurations.

Compared with Fullhan's U-Boot 2010.06, this is a modern driver-model port
rather than a copy of proprietary vendor code. It keeps the interfaces needed
by an existing vendor environment:

- `kload` reads the 3 MiB kernel partition from offset `0x50000`;
- `gpio <pin> out <0|1>` remains accepted in addition to current U-Boot GPIO
  syntax;
- the vendor `ethact=FH EMAC` value is discarded in memory so the current
  `eth0` device can be selected;
- `sf`, `bootm`, environment, memory, CRC, MII, ping and TFTP commands are
  available.

Vendor-only commands such as `upgrade`, `fastbootcmd`, `arc_go` and
`chpart` are not carried over. MMC/FAT commands are omitted from the compact
production target because the validated boot path uses SPI NOR. Long help,
line editing/completion, `tftpput` and optional TFTP tuning variables are
also omitted from that target to fit the immutable stock bootstrap envelope;
normal `help` and `tftpboot` remain. The larger RAM target retains development
and backup facilities including `tftpput`.

## Build

Install an ARM EABI cross compiler, Bison and Flex, then run:

```sh
CROSS_COMPILE=arm-linux-gnueabi- ./build.sh
```

The build creates these redistributable files in `output/`:

- `u-boot-fh8626v100.bin` — raw U-Boot binary;
- `u-boot-fh8626v100-bootstrap.bin` — generated 64 KiB Boot ROM container;
- `u-boot-fh8626v100-partition.bin` — padded 192 KiB U-Boot partition;
- `u-boot-fh8626v100-nor.bin` — complete 320 KiB OpenIPC boot region;
- `SHA256SUMS` — checksums for all generated binaries.

FH8626V100 Boot ROM does not load U-Boot directly. It first interprets a 64 KiB
container to initialize SDRAM and locate the U-Boot payload. Its recovered,
auditable board data is stored in
`board/fullhan/fh8626v100/bootrom.json`; no executable vendor binary is
embedded in the repository. The generator reproduces the validated stock
64 KiB container byte-for-byte, including the stock U-Boot descriptor. That
descriptor uses raw size `0x2bae4`, aligned size `0x2bb00` and JAMCRC
`0x251d4c31`. A four-byte correction in the alignment padding makes every
release satisfy that unchanged ROM-visible contract.

This is not a complete semantic reverse engineering of the Fullhan bootstrap
or the immutable Boot ROM interpreter. The manifest is a structured,
byte-exact reproduction of the known-working original container. The generated
container has been validated by successfully starting U-Boot and booting the
installed firmware on the target camera.

A verified 8 MiB flash dump can still be supplied as an independent validation
and recovery input:

```sh
FH8626_FLASH_BACKUP=/path/to/full-8m-backup.bin \
  CROSS_COMPILE=arm-linux-gnueabi- ./build.sh
```

The packer refuses corrupt dumps, inconsistent manifests and binaries larger
than the stock `0x2bb00` ROM envelope.

Migrating from the vendor boot chain updates only
`u-boot-fh8626v100-partition.bin` at `0x20000`.  The stock bootstrap remains
byte-for-byte unchanged, and the environment sector at `0x10000` is preserved.
The generated bootstrap file is a recovery/reference artifact and must not be
rewritten during a normal U-Boot update.

## Migrating from vendor firmware

Follow the complete, checksum-gated procedure in
[`fh8626v100-stock-migration.rst`](doc/board/fullhan/fh8626v100-stock-migration.rst).
The important rules are:

1. keep an externally recoverable, verified full-flash dump;
2. load the RAM target at `0xa3000000` from the vendor U-Boot;
3. validate SPI, kernel loading, GPIO and Ethernet without writing NOR;
4. write only the 192 KiB partition at `0x20000` and compare its complete
   read-back before resetting;
5. never erase the bootstrap at `0x00000` or environment at `0x10000` during
   this migration.

Do not TFTP the flash-linked raw binary to `0xa0800000` while the vendor U-Boot
is running: that is its active execution region. Use the RAM trampoline first,
and flash the padded partition artifact from a separate buffer.

The same method may work on other FH8626V100 boards, but only after their full
dump confirms the same bootstrap U-Boot descriptor, DDR parameter container,
flash geometry and load address. GPIO assignments, PHY wiring, memory size and
partition layouts are board-specific. A matching SoC name alone is not enough
to make persistent flashing safe.

## RAM validation

Build the non-persistent target with:

```sh
make O=build-ram CROSS_COMPILE=arm-linux-gnueabi- \
  fh8626v100_ram_defconfig
make O=build-ram CROSS_COMPILE=arm-linux-gnueabi- -j8
```

Load `build-ram/u-boot.bin` to `0xa3000000` from an existing U-Boot and start
it with `go 0xa3000000`. This validates a candidate without writing SPI NOR.

Detailed layout, migration and hardware-test instructions are in
[`doc/board/fullhan/fh8626v100.rst`](doc/board/fullhan/fh8626v100.rst).
The stock migration checklist is in
[`fh8626v100-stock-migration.rst`](doc/board/fullhan/fh8626v100-stock-migration.rst).
The recovered Boot ROM format is documented in
[`fh8626v100-boot-format.rst`](doc/board/fullhan/fh8626v100-boot-format.rst).

## Status

The production target has passed cold boot through the unchanged stock
bootstrap, persistent vendor-environment loading, repeated 3 MiB SPI NOR reads
at 50 MHz, legacy-image CRC verification, vendor-compatible GPIO setup,
100 Mbit/s full-duplex Ethernet, ping and TFTP. Both OpenIPC and the complete
installed stock firmware have booted through the port. The U-Boot-only
migration and read-back procedure was hardware-validated on 2026-09-04.
