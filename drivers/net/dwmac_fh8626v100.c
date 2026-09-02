// SPDX-License-Identifier: GPL-2.0+
/*
 * Fullhan FH8626V100 glue for the Synopsys Designware Ethernet MAC.
 */

#include <dm.h>
#include <linux/bitops.h>
#include <linux/delay.h>
#include <asm/io.h>
#include <phy.h>

#include "designware.h"

#define FH8626_PMU_BASE			0xf0000000
#define FH8626_PMU_SYS_CTRL		0x0c
#define FH8626_PMU_ETH_CTRL		0x28
#define FH8626_PMU_SWRST_AHB_CTRL	0x54
#define FH8626_ETH_SYS_CTRL		GENMASK(26, 24)
#define FH8626_ETH_SPEED_100M		BIT(2)
#define FH8626_EMAC_RESET		BIT(10)

static void fh8626_set_rmii_speed(int speed)
{
	void __iomem *reg = (void __iomem *)(FH8626_PMU_BASE +
					      FH8626_PMU_ETH_CTRL);

	if (speed == SPEED_10)
		clrbits_le32(reg, FH8626_ETH_SPEED_100M);
	else if (speed == SPEED_100)
		setbits_le32(reg, FH8626_ETH_SPEED_100M);
}

static int fh8626_emac_reset(void)
{
	void __iomem *reg = (void __iomem *)(FH8626_PMU_BASE +
					      FH8626_PMU_SWRST_AHB_CTRL);
	int timeout = 1000;

	writel(~FH8626_EMAC_RESET, reg);
	while (readl(reg) != 0xffffffff) {
		if (!timeout--)
			return -ETIMEDOUT;
		udelay(1);
	}

	return 0;
}

static int dwmac_fh8626_start(struct udevice *dev)
{
	struct eth_pdata *pdata = dev_get_plat(dev);
	struct dw_eth_dev *priv = dev_get_priv(dev);
	int ret;

	ret = designware_eth_init(priv, pdata->enetaddr);
	if (ret)
		return ret;

	fh8626_set_rmii_speed(priv->phydev->speed);

	return designware_eth_enable(priv);
}

static int dwmac_fh8626_probe(struct udevice *dev)
{
	int ret;

	/* Enable the MAC bus interface before reset. */
	setbits_le32((void __iomem *)(FH8626_PMU_BASE +
				      FH8626_PMU_SYS_CTRL),
		     FH8626_ETH_SYS_CTRL);

	/* Select 100 Mbit before releasing the MAC reset. */
	fh8626_set_rmii_speed(SPEED_100);
	ret = fh8626_emac_reset();
	if (ret)
		return ret;

	return designware_eth_probe(dev);
}

static const struct eth_ops dwmac_fh8626_ops = {
	.start		= dwmac_fh8626_start,
	.send		= designware_eth_send,
	.recv		= designware_eth_recv,
	.free_pkt	= designware_eth_free_pkt,
	.stop		= designware_eth_stop,
	.write_hwaddr	= designware_eth_write_hwaddr,
};

static const struct udevice_id dwmac_fh8626_ids[] = {
	{ .compatible = "fullhan,fh8626v100-dwmac" },
	{ }
};

U_BOOT_DRIVER(dwmac_fh8626) = {
	.name		= "dwmac_fh8626",
	.id		= UCLASS_ETH,
	.of_match	= dwmac_fh8626_ids,
	.of_to_plat	= designware_eth_of_to_plat,
	.probe		= dwmac_fh8626_probe,
	.ops		= &dwmac_fh8626_ops,
	.priv_auto	= sizeof(struct dw_eth_dev),
	.plat_auto	= sizeof(struct dw_eth_pdata),
	.flags		= DM_FLAG_ALLOC_PRIV_DMA,
};
