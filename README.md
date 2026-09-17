# OpenIPC U-Boot for ANJIA AJL33PQ0866 / FH8626V100

This repository carries a modern U-Boot port for the Fullhan FH8626V100 as
validated on the ANJIA AJL33PQ0866 camera. The implementation uses current
U-Boot driver model and device tree support for UART, timer, GPIO, SPI NOR and
RMII Ethernet.

The target architecture is **OpenIPC-native**. Factory Fullhan layout and
commands are retained only as migration/recovery knowledge; they are not the
production contract.

## Target OpenIPC layout

The 8 MiB NOR layout follows the standard OpenIPC geometry:

| Region | Offset | Size |
|---|---:|---:|
| boot | `0x000000` | 256 KiB |
| env | `0x040000` | 64 KiB |
| kernel | `0x050000` | 2048 KiB |
| rootfs | `0x250000` | 5120 KiB |
| rootfs_data | `0x750000` | remainder |

FH8626V100 has one board-specific detail inside the standard 256 KiB `boot`
partition:

- `0x00000..0x0ffff`: 64 KiB Fullhan Boot ROM data container;
- `0x10000..0x3ffff`: 192 KiB current U-Boot payload.

The persistent U-Boot environment is therefore at the standard OpenIPC offset
`0x40000`. Linux still starts at `0x50000`, matching the normal OpenIPC 8 MiB
layout.

The recovered ANJIA Boot ROM data is represented as auditable JSON in
`board/fullhan/fh8626v100/bootrom.json`. The native packer changes only the
ROM-visible U-Boot contract required by the OpenIPC layout: U-Boot moves to
`0x10000` and occupies a fixed 192 KiB envelope. Load and entry remain
`0xa0800000`.

## OpenIPC environment

The production target uses OpenIPC-style variables and commands, including:

- `soc=fh8626v100`;
- `manufacturer=fullhan`;
- `baseaddr=0xa1000000`;
- `flashsize=0x800000`;
- `osmem=39M` and `totalmem=64M`;
- `mtdpartsnor8m` and `setnor8m`;
- `bootcmdnor`;
- `uknor8m` and `urnor8m`;
- `uImage.${soc}` and `rootfs.squashfs.${soc}` update names.

The production build does not depend on the Fullhan factory environment,
`kload`, `ethact=FH EMAC`, or the factory `gpio <pin> out <0|1>` command syntax.
Those compatibility helpers are opt-in and enabled only in the RAM migration
target.

## Board scope

Do not treat the generated boot image as a universal FH8626V100 binary.
ANJIA AJL33PQ0866 has board-specific DDR/Boot-ROM parameters, RMII wiring and
flash migration constraints. Another FH8626V100 board should reuse the SoC
support but provide and validate its own board data before persistent flashing.

## Build

Install an ARM EABI cross compiler, Bison and Flex, then run:

```sh
CROSS_COMPILE=arm-linux-gnueabi- ./build.sh
```

The build emits board-specific artifacts in `output/`:

- `u-boot-fh8626v100-anjia-ajl33pq0866.bin` — 256 KiB OpenIPC `boot` partition;
- `u-boot-fh8626v100-anjia-ajl33pq0866-bootstrap.bin` — 64 KiB ROM container;
- `u-boot-fh8626v100-anjia-ajl33pq0866-uboot.bin` — padded 192 KiB U-Boot payload;
- `u-boot-fh8626v100-anjia-ajl33pq0866-raw.bin` — raw linked U-Boot binary;
- `u-boot-fh8626v100-anjia-ajl33pq0866-ram.bin` — non-persistent migration/recovery target;
- `SHA256SUMS` — hashes for all generated artifacts.

The production packer is `tools/fh8626_openipc_boot.py`. The older
`tools/fh8626_bootchain.py` remains the stock-container parser/reconstruction
oracle and is used for migration evidence, not to define the final OpenIPC
partition layout.

## Migration from factory firmware

Moving from factory Fullhan firmware to the native OpenIPC layout is a one-time
full-layout migration, not a U-Boot-only update. The old environment at
`0x10000` and old U-Boot at `0x20000` are replaced by the 256 KiB OpenIPC boot
partition and a new environment at `0x40000`.

Do not reset after writing only the bootloader. Before the first native cold
boot, the target must also contain an OpenIPC kernel fitting the 2 MiB kernel
partition and an OpenIPC rootfs fitting the 5 MiB rootfs partition.

Use the RAM target and keep an externally verified full-flash backup plus an
SPI programmer available. The detailed procedure is in
`doc/board/fullhan/fh8626v100-openipc-migration.rst`.

## Hardware status

The underlying U-Boot port is hardware-proven on AJL33PQ0866 for UART, 64 MiB
DRAM, GPIO, repeated SPI NOR reads, legacy kernel handoff, RMII Ethernet,
ping/TFTP, persistent environment access and cold boot. The earlier
stock-compatible replacement U-Boot has booted both OpenIPC and the complete
installed factory firmware.

The **OpenIPC-native relocation** of U-Boot to `0x10000`, environment to
`0x40000`, and rootfs to `0x250000` is a new integration candidate and must not
be called `HARDWARE_PASS` until the complete migrated layout has cold-booted on
the camera.

## Documentation

- `doc/board/fullhan/fh8626v100.rst` — platform and OpenIPC boot contract;
- `doc/board/fullhan/fh8626v100-openipc-migration.rst` — one-time native layout migration;
- `doc/board/fullhan/fh8626v100-stock-migration.rst` — historical stock-compatible migration reference;
- `doc/board/fullhan/fh8626v100-boot-format.rst` — recovered Fullhan Boot ROM container format.
