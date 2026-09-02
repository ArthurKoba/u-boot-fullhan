// SPDX-License-Identifier: GPL-2.0+
/*
 * Fullhan FH8626V100 reference platform
 *
 * The RAM target is entered after the vendor bootstrap has initialized
 * clocks and the 64 MiB SDRAM window at 0xa0000000.
 */

#include <init.h>
#include <asm/global_data.h>
#include <asm/io.h>

#define FH8626_PMU_BASE		0xf0000000
#define FH8626_PMU_SW_RESET	(FH8626_PMU_BASE + 0x4c)

#define FH8626_SDRAM_BASE	0xa0000000
#define FH8626_SDRAM_SIZE	0x04000000
#define FH8626_BOOT_PARAMS	(FH8626_SDRAM_BASE + 0x100)

DECLARE_GLOBAL_DATA_PTR;

int board_init(void)
{
	gd->bd->bi_boot_params = FH8626_BOOT_PARAMS;

	return 0;
}

int dram_init(void)
{
	gd->ram_size = FH8626_SDRAM_SIZE;

	return 0;
}

int dram_init_banksize(void)
{
	gd->dram[0].start = FH8626_SDRAM_BASE;
	gd->dram[0].size = FH8626_SDRAM_SIZE;

	return 0;
}

void reset_cpu(void)
{
	writel(0x7fffffff, FH8626_PMU_SW_RESET);

	while (1)
		;
}
