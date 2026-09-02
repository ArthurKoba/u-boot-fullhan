/* SPDX-License-Identifier: GPL-2.0+ */

#include <linux/linkage.h>

ENTRY(lowlevel_init)
	/* The ROM-loaded bootstrap configures SDRAM before entering U-Boot. */
	bx	lr
ENDPROC(lowlevel_init)
