/* SPDX-License-Identifier: GPL-2.0+ */

#include <linux/linkage.h>

ENTRY(lowlevel_init)
	/* The vendor bootstrap has already configured clocks and SDRAM. */
	bx	lr
ENDPROC(lowlevel_init)
