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

The build always creates these redistributable files in `output/`:

- `u-boot-fh8626v100.bin` — raw U-Boot binary;
- `u-boot-fh8626v100-partition.bin` — padded 192 KiB U-Boot partition;
- `SHA256SUMS` — checksums for all generated binaries.

FH8626V100 Boot ROM does not load U-Boot directly. It first executes a 64 KiB
board bootstrap which initializes SDRAM and describes the U-Boot payload. No
redistributable source for that bootstrap is available, so it is deliberately
not included in this repository.

To create the complete OpenIPC `u-boot-fh8626v100-nor.bin` release asset from
your own verified 8 MiB flash dump:

```sh
FH8626_FLASH_BACKUP=/path/to/full-8m-backup.bin \
  CROSS_COMPILE=arm-linux-gnueabi- ./build.sh
```

The packer validates the original bootstrap descriptor and JAMCRC before
patching it for the newly built U-Boot. It refuses corrupt dumps and binaries
larger than the fixed 192 KiB slot.

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

## Status

The production target has passed cold boot, persistent environment, repeated
3 MiB SPI NOR reads at 50 MHz, legacy-image CRC verification, GPIO setup,
100 Mbit/s full-duplex Ethernet, TFTP and OpenIPC flash-root boot.
