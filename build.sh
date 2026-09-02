#!/bin/sh
# SPDX-License-Identifier: GPL-2.0+

set -eu

src_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
build_dir=${BUILD_DIR:-"$src_dir/build-fh8626v100"}
output_dir=${OUTPUT_DIR:-"$src_dir/output"}
cross_compile=${CROSS_COMPILE:-arm-linux-gnueabi-}

mkdir -p "$build_dir" "$output_dir"
rm -f "$output_dir"/u-boot-fh8626v100.bin \
	"$output_dir"/u-boot-fh8626v100-bootstrap.bin \
	"$output_dir"/u-boot-fh8626v100-nor.bin \
	"$output_dir"/u-boot-fh8626v100-partition.bin \
	"$output_dir"/SHA256SUMS

make -C "$src_dir" O="$build_dir" \
	CROSS_COMPILE="$cross_compile" fh8626v100_flash_defconfig
make -C "$src_dir" O="$build_dir" \
	CROSS_COMPILE="$cross_compile" -j"${JOBS:-$(nproc)}"

install -m 0644 "$build_dir/u-boot.bin" \
	"$output_dir/u-boot-fh8626v100.bin"

if [ -n "${FH8626_FLASH_BACKUP:-}" ]; then
	python3 "$src_dir/tools/fh8626_bootchain.py" \
		--flash-backup "$FH8626_FLASH_BACKUP" \
		"$output_dir/u-boot-fh8626v100.bin" \
		"$output_dir"
else
	python3 "$src_dir/tools/fh8626_bootchain.py" \
		"$output_dir/u-boot-fh8626v100.bin" \
		"$output_dir"
fi

(
	cd "$output_dir"
	sha256sum u-boot-fh8626v100*.bin > SHA256SUMS
)
