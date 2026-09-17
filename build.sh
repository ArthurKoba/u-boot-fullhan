#!/bin/sh
# SPDX-License-Identifier: GPL-2.0+

set -eu

src_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
build_dir=${BUILD_DIR:-"$src_dir/build-fh8626v100"}
ram_build_dir=${RAM_BUILD_DIR:-"$src_dir/build-fh8626v100-ram"}
output_dir=${OUTPUT_DIR:-"$src_dir/output"}
cross_compile=${CROSS_COMPILE:-arm-linux-gnueabi-}
bootstrap_manifest=${FH8626_BOOTSTRAP_MANIFEST:-"$src_dir/board/fullhan/fh8626v100/bootrom.json"}
prefix=u-boot-fh8626v100-anjia-ajl33pq0866

python3 "$src_dir/test/py/tests/test_fh8626_openipc_boot.py"

mkdir -p "$build_dir" "$ram_build_dir" "$output_dir"
rm -f "$output_dir"/"$prefix"*.bin "$output_dir"/SHA256SUMS

make -C "$src_dir" O="$build_dir" \
	CROSS_COMPILE="$cross_compile" fh8626v100_flash_defconfig
make -C "$src_dir" O="$build_dir" \
	CROSS_COMPILE="$cross_compile" -j"${JOBS:-$(nproc)}"

install -m 0644 "$build_dir/u-boot.bin" \
	"$output_dir/$prefix-raw.bin"

python3 "$src_dir/tools/fh8626_openipc_boot.py" \
	--bootstrap-manifest "$bootstrap_manifest" \
	"$output_dir/$prefix-raw.bin" "$output_dir"
python3 "$src_dir/tools/fh8626_openipc_boot.py" \
	"$output_dir/$prefix-nor.bin" --inspect

make -C "$src_dir" O="$ram_build_dir" \
	CROSS_COMPILE="$cross_compile" fh8626v100_ram_defconfig
make -C "$src_dir" O="$ram_build_dir" \
	CROSS_COMPILE="$cross_compile" -j"${JOBS:-$(nproc)}"
install -m 0644 "$ram_build_dir/u-boot.bin" \
	"$output_dir/$prefix-ram.bin"

(
	cd "$output_dir"
	sha256sum "$prefix"*.bin > SHA256SUMS
)
