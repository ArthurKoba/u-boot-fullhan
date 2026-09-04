// SPDX-License-Identifier: GPL-2.0+
/* Commands required by the persistent Fullhan vendor environment. */

#include <command.h>

static int do_fh8626_kload(struct cmd_tbl *cmdtp, int flag, int argc,
			   char *const argv[])
{
	puts("load kernel 0x00050000(0x00300000) to 0xa1000000\n");

	return run_command("sf probe 0:0 50000000; "
			   "sf read 0xa1000000 0x50000 0x300000", 0);
}

U_BOOT_CMD(kload, 1, 0, do_fh8626_kload,
	   "load the stock kernel partition from SPI NOR", "");
