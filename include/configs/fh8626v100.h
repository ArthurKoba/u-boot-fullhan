/* SPDX-License-Identifier: GPL-2.0+ */
#ifndef __CONFIG_FH8626V100_H
#define __CONFIG_FH8626V100_H

#define CFG_SYS_SDRAM_BASE	0xa0000000
#define CFG_SYS_UBOOT_BASE	CONFIG_TEXT_BASE

#define CFG_EXTRA_ENV_SETTINGS \
	"console=ttyS0,115200\0" \
	"osmem=39M\0" \
	"totalmem=64M\0" \
	"bootm_low=0xa0000000\0" \
	"bootm_size=0x02700000\0" \
	"soc=fh8626v100\0" \
	"board=anjia-ajl33pq0866\0" \
	"manufacturer=fullhan\0" \
	"baseaddr=0xa1000000\0" \
	"flashsize=0x800000\0" \
	"kernaddr=0x50000\0" \
	"kernsize=0x200000\0" \
	"rootaddr=0x250000\0" \
	"rootsize=0x500000\0" \
	"rootmtd=5120k\0" \
	"ipaddr=192.168.1.10\0" \
	"serverip=192.168.1.254\0" \
	"netmask=255.255.255.0\0" \
	"gatewayip=192.168.1.1\0" \
	"extras=\0" \
	"updatetool=tftpboot\0" \
	"mtdparts=spi_flash:256k(boot),64k(env),2048k(kernel)," \
		"5120k(rootfs),-(rootfs_data)\0" \
	"mtdpartsnor8m=setenv rootmtd 5120k; setenv rootsize 0x500000; " \
		"setenv rootaddr 0x250000; setenv mtdparts " \
		"spi_flash:256k(boot),64k(env),2048k(kernel)," \
		"5120k(rootfs),-(rootfs_data)\0" \
	"bootargs=mem=${osmem} console=${console} panic=20 " \
		"root=/dev/mtdblock3 rootfstype=squashfs ro init=/init " \
		"mtdparts=${mtdparts} ethaddr=${ethaddr} ${extras}\0" \
	"cmdnor=sf probe 0; setenv setargs setenv bootargs ${bootargs}; " \
		"run setargs; sf read ${baseaddr} ${kernaddr} ${kernsize}; " \
		"bootm ${baseaddr}\0" \
	"bootcmdnor=run cmdnor\0" \
	"setnor8m=run mtdpartsnor8m; setenv bootcmd ${bootcmdnor}; " \
		"saveenv; reset\0" \
	"ubootfile=u-boot-${soc}-${board}-nor.bin\0" \
	"ubnor=${updatetool} ${baseaddr} ${ubootfile} && run ubwrite\0" \
	"ubwrite=sf probe 0; sf erase 0x0 ${kernaddr}; " \
		"sf write ${baseaddr} 0x0 ${kernaddr}\0" \
	"uknor=${updatetool} ${baseaddr} uImage.${soc} && run ukwrite\0" \
	"ukwrite=sf probe 0; sf erase ${kernaddr} ${kernsize}; " \
		"sf write ${baseaddr} ${kernaddr} ${filesize}\0" \
	"urnor=${updatetool} ${baseaddr} rootfs.squashfs.${soc} && run urwrite\0" \
	"urwrite=sf probe 0; sf erase ${rootaddr} ${rootsize}; " \
		"sf write ${baseaddr} ${rootaddr} ${filesize}\0" \
	"netboot=${updatetool} ${baseaddr} uImage.${soc}; bootm ${baseaddr}\0"

#endif
