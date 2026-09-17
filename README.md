# OpenIPC U-Boot for ANJIA AJL33PQ0866 / FH8626V100

This repository carries a modern U-Boot port for the Fullhan FH8626V100 as
validated on the ANJIA AJL33PQ0866 camera. The implementation uses current
U-Boot driver model and device tree support for UART, timer, GPIO, SPI NOR and
RMII Ethernet.

The target architecture is **OpenIPC-native**. Factory Fullhan layout and
commands are retained only as migration/recovery knowledge; they are not the
production contract.

## Repository policy for generated binaries

Generated firmware/U-Boot binaries are **not committed to this source
repository**. The repository keeps source, board data, packers, validators,
tests, build scripts, documentation and provenance/hash references. Generated
`*.bin`, `*.img`, `*.elf`, `/output/` and build directories are ignored by Git.

For active hardware work, generated files belong in the ignored local
`output/` directory. For long-term retention or release, use a dedicated
artifact/release/evidence store rather than committing generated binaries to
the source tree. See
`doc/board/fullhan/fh8626v100-history.rst` for the durable engineering history
and artifact policy.

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
- `0x10000..0x3ffff`: 192 KiB physical U-Boot slot.

The persistent U-Boot environment is at the OpenIPC offset `0x40000`. Linux
starts at `0x50000`, matching the normal OpenIPC 8 MiB layout.

The recovered ANJIA Boot ROM data is represented as auditable JSON in
`board/fullhan/fh8626v100/bootrom.json`. The native packer moves U-Boot to
`0x10000` while preserving its RAM load/entry address at `0xa0800000`. For each
build it records the actual raw U-Boot size, aligns the ROM-visible payload to
`0x100`, and calculates the descriptor JAMCRC from that payload. The remaining
bytes in the 192 KiB physical slot stay erased.

## OpenIPC environment

The production target follows the current OpenIPC NOR environment conventions,
including:

- `soc=fh8626v100`, `board=anjia-ajl33pq0866`, `manufacturer=fullhan`;
- `baseaddr`, `flashsize`, `osmem` and `totalmem`;
- `kernaddr=0x50000`, `kernsize=0x200000`;
- `rootaddr=0x250000`, `rootsize=0x500000`;
- `mtdpartsnor8m`, `setnor8m`, `cmdnor` and `bootcmdnor`;
- `updatetool=tftpboot`;
- `ubnor` / `ubwrite`, `uknor` / `ukwrite`, and `urnor` / `urwrite`.

The U-Boot updater deliberately uses a board-qualified artifact name:

`u-boot-fh8626v100-anjia-ajl33pq0866-nor.bin`

because the reconstructed Boot ROM/DDR data is proven only on AJL33PQ0866.
Kernel and rootfs retain the normal OpenIPC SoC-qualified names
`uImage.fh8626v100` and `rootfs.squashfs.fh8626v100`.

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

`build.sh` runs the native boot-artifact unit tests, builds both production and
RAM-recovery configurations, validates the generated native NOR artifact, and
then produces `SHA256SUMS`.

The build emits these board-specific files in ignored `output/` storage:

- `u-boot-fh8626v100-anjia-ajl33pq0866-nor.bin` — 320 KiB OpenIPC updater image: 256 KiB `boot` plus an erased 64 KiB `env` sector;
- `u-boot-fh8626v100-anjia-ajl33pq0866-boot.bin` — 256 KiB `boot` partition only;
- `u-boot-fh8626v100-anjia-ajl33pq0866-bootstrap.bin` — 64 KiB ROM container;
- `u-boot-fh8626v100-anjia-ajl33pq0866-uboot.bin` — U-Boot payload padded to the 192 KiB physical slot;
- `u-boot-fh8626v100-anjia-ajl33pq0866-raw.bin` — raw linked U-Boot binary;
- `u-boot-fh8626v100-anjia-ajl33pq0866-ram.bin` — non-persistent migration/recovery target;
- `SHA256SUMS` — hashes for all generated artifacts.

The production packer is `tools/fh8626_openipc_boot.py`. The older
`tools/fh8626_bootchain.py` remains the stock-container parser/reconstruction
oracle and migration evidence tool; it does not define the final OpenIPC flash
layout.

## Migration from factory firmware

Moving from factory Fullhan firmware to the native OpenIPC layout is a one-time
full-layout migration, not a U-Boot-only update. The old environment at
`0x10000` and old U-Boot at `0x20000` are replaced by the OpenIPC boot image:

- Boot ROM data at `0x00000`;
- U-Boot at `0x10000`;
- erased/new OpenIPC environment at `0x40000`.

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

The current native production build fits the 192 KiB physical U-Boot slot while
retaining TFTP upload, TFTP variables, command-line editing, autocomplete, long
help and `sleep`. Final acceptance still depends on the target OpenIPC kernel
fitting the standard 2 MiB kernel partition and on a physical cold-boot
migration test.

## OpenIPC alignment

Before contribution or release, re-check the live OpenIPC rules and U-Boot
conventions rather than treating this README as upstream authority:

- https://github.com/OpenIPC/wiki/blob/master/en/help-uboot.md
- https://github.com/OpenIPC/firmware
- https://github.com/OpenIPC

OpenIPC source ownership for a Fullhan U-Boot repository is an upstream
organizational decision. U-Boot source must not be copied into Firmware or
Builder merely to make integration convenient.

## Documentation

- `doc/board/fullhan/fh8626v100.rst` — platform and OpenIPC boot contract;
- `doc/board/fullhan/fh8626v100-openipc-migration.rst` — one-time native layout migration;
- `doc/board/fullhan/fh8626v100-stock-migration.rst` — historical stock-compatible migration reference;
- `doc/board/fullhan/fh8626v100-boot-format.rst` — recovered Fullhan Boot ROM container format;
- `doc/board/fullhan/fh8626v100-history.rst` — engineering history and generated-artifact policy.
