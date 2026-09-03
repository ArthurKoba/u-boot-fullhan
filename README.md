# OpenIPC U-Boot for Fullhan FH8626V100

This repository contains a current-upstream U-Boot port for the Fullhan
FH8626V100 camera SoC. It provides UART, 64 MiB DRAM, GPIO, SPI NOR and RMII
Ethernet support, plus an OpenIPC-compatible default environment.

The port is hardware-tested on an ANJIA AJL33PQ0866 camera with an 8 MiB
MX25L6405D NOR flash. Both a non-persistent RAM target and a production flash
target are available.

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
container to initialize SDRAM and locate the U-Boot payload. Its
recovered, auditable board data is stored in
`board/fullhan/fh8626v100/bootrom.json`; no executable vendor binary is
embedded in the repository. The generator reproduces the validated stock
64 KiB container byte-for-byte apart from the confirmed U-Boot descriptor.
That descriptor uses a permanent 192 KiB envelope and a fixed JAMCRC; a
four-byte correction stored at the end of each U-Boot partition makes every
release satisfy the same ROM-visible contract.

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
than the fixed 192 KiB slot.

Migrating from the vendor boot chain is a one-time paired update: install and
verify the fixed-envelope partition first, install and verify the generated
bootstrap last, and reset only after both comparisons pass.  After that first
successful cold boot, the bootstrap is invariant and future releases update
only `u-boot-fh8626v100-partition.bin`.  Preserve the environment sector at
`0x10000` unless an environment reset is explicitly intended.  A vendor
bootstrap and a fixed-envelope partition are not compatible.

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
The recovered Boot ROM format is documented in
[`fh8626v100-boot-format.rst`](doc/board/fullhan/fh8626v100-boot-format.rst).

## Status

The production target has passed cold boot, persistent environment, repeated
3 MiB SPI NOR reads at 50 MHz, legacy-image CRC verification, GPIO setup,
100 Mbit/s full-duplex Ethernet, TFTP and OpenIPC flash-root boot.
The permanent fixed-envelope update contract is machine-tested and awaits its
first cold-boot hardware validation after recovery of the development camera.
