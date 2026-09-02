// SPDX-License-Identifier: GPL-2.0+
/*
 * Fullhan FH8626V100 cold-boot clock and reset setup.
 */

#include <init.h>
#include <asm/io.h>

#define FH8626_PMU_BASE		0xf0000000
int arch_cpu_init(void)
{
	void __iomem *pmu = (void __iomem *)FH8626_PMU_BASE;

	/* Reproduce the vendor U-Boot clock/reset pulse before DM and UART. */
	setbits_le32(pmu + 0x1c, 0x120a2280);
	setbits_le32(pmu + 0x20, 0x000001c0);
	clrbits_le32(pmu + 0x24, 0x00006000);
	clrsetbits_le32(pmu + 0x2c, 0x00000f00, 0x00000100);
	clrsetbits_le32(pmu + 0x2c, 0x0f000000, 0x01000000);
	clrsetbits_le32(pmu + 0x30, 0x0000001f, 0x00000005);
	clrsetbits_le32(pmu + 0x38, 0x000000ff, 0x00000063);
	clrsetbits_le32(pmu + 0x38, 0x00ff0000, 0x00630000);
	clrsetbits_le32(pmu + 0x38, 0x0000ff00, 0x00007f00);
	clrbits_le32(pmu + 0x1c, 0x120a2280);
	clrbits_le32(pmu + 0x20, 0x000001c0);
	clrbits_le32(pmu + 0x20, 0x00000002);
	clrbits_le32(pmu + 0x210, BIT(31));

	return 0;
}
