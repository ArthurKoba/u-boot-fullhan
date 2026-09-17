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
	"manufacturer=fullhan\0" \
	"baseaddr=0xa1000000\0" \
	"flashsize=0x800000\0" \
	"ipaddr=192.168.1.10\0" \
	"serverip=192.168.1.254\0" \
	"extras=\0" \
	"mtdparts=spi_flash:256k(boot),64k(env),2048k(kernel)," \
		"5120k(rootfs),-(rootfs_data)\0" \
	"mtdpartsnor8m=setenv mtdparts " \
		"spi_flash:256k(boot),64k(env),2048k(kernel)," \
		"5120k(rootfs),-(rootfs_data)\0" \
	"bootargs=mem=${osmem} console=${console} panic=20 " \
		"root=/dev/mtdblock3 rootfstype=squashfs ro init=/init " \
		"mtdparts=${mtdparts} ethaddr=${ethaddr} ${extras}\0" \
	"bootcmdnor=setenv setargs setenv bootargs ${bootargs}; " \
		"run setargs; sf probe 0:0; " \
		"sf read ${baseaddr} 0x50000 0x200000; bootm ${baseaddr}\0" \
	"setnor8m=run mtdpartsnor8m; setenv bootcmd ${bootcmdnor}; " \
		"saveenv; reset\0" \
	"uknor8m=mw.b ${baseaddr} ff 0x200000; " \
		"tftpboot ${baseaddr} uImage.${soc} && sf probe 0:0; " \
		"sf erase 0x50000 0x200000; " \
		"sf write ${baseaddr} 0x50000 ${filesize}\0" \
	"urnor8m=mw.b ${baseaddr} ff 0x500000; " \
		"tftpboot ${baseaddr} rootfs.squashfs.${soc} && sf probe 0:0; " \
		"sf erase 0x250000 0x500000; " \
		"sf write ${baseaddr} 0x250000 ${filesize}\0" \
	"netboot=tftpboot ${baseaddr} uImage.${soc}; bootm ${baseaddr}\0"

#endif
