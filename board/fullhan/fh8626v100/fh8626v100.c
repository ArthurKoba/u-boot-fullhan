// SPDX-License-Identifier: GPL-2.0+
/*
 * Fullhan FH8626V100 reference platform
 *
 * The RAM target is entered after the vendor bootstrap has initialized
 * clocks and the 64 MiB SDRAM window at 0xa0000000.
 */

#include <init.h>
#include <linux/bitops.h>
#include <linux/delay.h>
#include <asm/global_data.h>
#include <asm/io.h>

#define FH8626_PMU_BASE		0xf0000000
#define FH8626_PMU_SW_RESET	(FH8626_PMU_BASE + 0x4c)
#define FH8626_PAD_BASE		(FH8626_PMU_BASE + 0x80)
#define FH8626_GPIO0_BASE	0xf0300000
#define FH8626_GPIO1_BASE	0xf4000000
#define FH8626_GPIO_SWPORTA_DR	0x00
#define FH8626_GPIO_SWPORTA_DDR	0x04

#define FH8626_SDRAM_BASE	0xa0000000
#define FH8626_SDRAM_SIZE	0x04000000
#define FH8626_BOOT_PARAMS	(FH8626_SDRAM_BASE + 0x100)

DECLARE_GLOBAL_DATA_PTR;

static void fh8626_gpio_output(void __iomem *base, unsigned int pin,
			       bool value)
{
	setbits_le32(base + FH8626_GPIO_SWPORTA_DDR, BIT(pin));
	if (value)
		setbits_le32(base + FH8626_GPIO_SWPORTA_DR, BIT(pin));
	else
		clrbits_le32(base + FH8626_GPIO_SWPORTA_DR, BIT(pin));
}

static void fh8626_pad_config(unsigned int pad, u32 config)
{
	writel(config, (void __iomem *)(FH8626_PAD_BASE + pad * sizeof(u32)));
}

static void fh8626_rmii_pinctrl_init(void)
{
	/* FH8626V100 RMII pad configuration. */
	fh8626_pad_config(15, 0x10011140); /* MAC_RMII_CLK */
	fh8626_pad_config(16, 0x10001140); /* MAC_REF_CLK */
	fh8626_pad_config(17, 0x10011140); /* MAC_MDC */
	fh8626_pad_config(18, 0x10001100); /* MAC_MDIO */
	fh8626_pad_config(22, 0x10011100); /* MAC_RXD_0 */
	fh8626_pad_config(23, 0x10011100); /* MAC_RXD_1 */
	fh8626_pad_config(26, 0x10011100); /* MAC_RXDV */
	fh8626_pad_config(28, 0x10001100); /* MAC_TXD_0 */
	fh8626_pad_config(29, 0x10001100); /* MAC_TXD_1 */
	fh8626_pad_config(32, 0x10001100); /* MAC_TXEN */
	fh8626_pad_config(46, 0x11011100); /* GPIO11: external PHY reset */
}

static void fh8626_board_io_init(void)
{
	void __iomem *pmu = (void __iomem *)FH8626_PMU_BASE;

	fh8626_rmii_pinctrl_init();

	/* Enable the external PHY and pulse its reset before driver probing. */
	writel(0x01101030, pmu + 0xe8);
	fh8626_gpio_output((void __iomem *)FH8626_GPIO1_BASE, 9, false);
	fh8626_gpio_output((void __iomem *)FH8626_GPIO0_BASE, 11, true);
	udelay(150000);
	fh8626_gpio_output((void __iomem *)FH8626_GPIO0_BASE, 11, false);
	udelay(10000);
	fh8626_gpio_output((void __iomem *)FH8626_GPIO0_BASE, 11, true);
	writel(0x00101030, pmu + 0xe8);
}

int board_init(void)
{
	fh8626_board_io_init();
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
