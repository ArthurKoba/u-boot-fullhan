/* SPDX-License-Identifier: GPL-2.0+ */
#ifndef __CONFIG_FH8626V100_H
#define __CONFIG_FH8626V100_H

#define CFG_SYS_SDRAM_BASE	0xa0000000
#define CFG_SYS_UBOOT_BASE	CONFIG_TEXT_BASE

#define CFG_EXTRA_ENV_SETTINGS \
	"console=ttyS0,115200\0" \
	"mem=39M\0" \
	"bootm_low=0xa0000000\0" \
	"bootm_size=0x02700000\0" \
	"soc=fh8626v100\0" \
	"manufacturer=fullhan\0" \
	"baseaddr=0xa1000000\0" \
	"flashsize=0x800000\0" \
	"kern_len=0x300000\0" \
	"ipaddr=192.168.1.203\0" \
	"serverip=192.168.1.11\0" \
	"bootfile=anjia-ajl33pq0866.uImage\0" \
	"set_gpio=gpio set 23; gpio clear 0; gpio clear 1; " \
		"gpio clear 2; gpio clear 3; gpio clear 7; " \
		"gpio clear 6; gpio clear 50; gpio clear 51; " \
		"gpio clear 18; gpio clear 60\0" \
	"openipc_args=setenv bootargs console=${console} mem=${mem} " \
		"panic=20 mtdparts=${mtdparts} root=/dev/mtdblock5 " \
		"rootfstype=squashfs ro init=/init\0" \
	"openipc_boot=run set_gpio; run openipc_args; sf probe 0:0; " \
		"sf read ${baseaddr} 0x050000 ${kern_len}; " \
		"bootm ${baseaddr}\0" \
	"bootcmdnor=run openipc_boot\0" \
	"netboot=run set_gpio; run openipc_args; " \
		"tftpboot ${baseaddr} ${bootfile}; " \
		"bootm ${baseaddr}\0"

#endif
