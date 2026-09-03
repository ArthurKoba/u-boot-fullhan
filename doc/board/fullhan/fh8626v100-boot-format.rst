.. SPDX-License-Identifier: GPL-2.0+

FH8626V100 Boot ROM container
============================

Scope and evidence
------------------

The first 64 KiB of the FH8626V100 SPI NOR is a data container consumed before
U-Boot starts.  It is not a second U-Boot.  No ARM instructions or executable
payload have been identified in this board's container.

This work does not claim a complete semantic reverse engineering of the
Fullhan bootstrap protocol or its immutable mask-ROM interpreter.  The
checked-in manifest is a structured, byte-exact reproduction of the validated
working original.  Only meanings supported by binary structure, cross-sample
comparison or executable loader code are documented as recovered.  Unknown
fields are retained unchanged.  A container produced by this method has
successfully started the ported U-Boot and loaded the installed firmware on
the target FH8626V100 camera.

The format below was recovered from the validated ANJIA AJL33PQ0866 8 MiB NOR
dump with SHA256
``db489511bcc678f7b8fa75497ac29ca51a882269d6646b24325560fecf60da67``.
The descriptor layout, alignment, checksum and parameter-record structure were
cross-checked against the independently acquired FH8852V201 image published at
``https://github.com/pavliha/fh8852v201-dump``.  Its ``uboot.bin`` SHA256 is
``c24b1ec9f4a173d4282d8fdf81bde5fbfabd4bfcf4e3755e4e0098e2bedda85e``.
The FH8852V201 image contains an executable intermediate RAM stage.  Its ARM
code was mapped at ``0x10008000`` and analysed independently with Ghidra and
GNU objdump.  That code provides direct evidence for the descriptor-table
walk, payload loading and checksum checks.  Meanings which can only be
implemented by the immutable mask ROM remain marked as inferred.

Container header
----------------

All integers are little-endian.  Bytes not listed below are reserved or board
metadata and must be preserved until their ROM semantics are known.

.. list-table::
   :header-rows: 1

   * - Offset
     - Size
     - Meaning
   * - 0x0000
     - 4
     - Magic ``2BL*``.
   * - 0x0004
     - 4
     - Product identifier; ``0x11170866`` on the validated board.
   * - 0x0008
     - 4
     - Format/platform selector.  It is ``0x64`` on FH8626V100 and ``1`` on
       FH8852V201; its exact interpretation is unknown.
   * - 0x000c
     - 4
     - Number of descriptors handled by the selected load stage.
   * - 0x0010
     - 4
     - Number of leading parameter/pre-load descriptors handled before that
       stage.
   * - 0x0014
     - 4
     - Header size and end of the descriptor table, ``0x280``.
   * - 0x0018
     - 4
     - Marker ``0xaa5555aa``; security/boot-mode meaning is inferred.
   * - 0x005c
     - 4
     - NOR capacity, ``0x00800000``.
   * - 0x0060
     - 0xa0
     - Fixed-size product, board, version and release strings.
   * - 0x0100
     - variable
     - Array of 64-byte image descriptors.

The total descriptor count is ``(header_size - 0x100) / 0x40`` and equals the
sum of the two counts at 0x0c and 0x10 in both known samples.  This is also
confirmed by the FH8852 RAM stage: it reads their sum multiplied by 0x40,
then starts its table walk after the leading count.  The FH8626V100
image has six descriptors: ``param``, ``uboot``, ``kernel``, ``data``, ``res``
and ``app``.  Only ``param`` and ``uboot`` are required by the replacement
boot chain; removing the remaining table entries has not yet been tested.

Image descriptor
----------------

Each descriptor is 64 bytes:

.. list-table::
   :header-rows: 1

   * - Offset
     - Size
     - Meaning
   * - 0x00
     - 16
     - NUL-terminated image name.
   * - 0x10
     - 4
     - Selector.  It distinguishes the three DDR profiles in the FH8852V201
       sample and is zero on FH8626V100; exact mask-ROM semantics are unknown.
   * - 0x14
     - 4
     - Reserved.
   * - 0x18
     - 4
     - Exact payload size.  Zero for the ``param`` table.
   * - 0x1c
     - 4
     - Reserved.
   * - 0x20
     - 4
     - Stored size, padded to a 128-byte boundary.
   * - 0x24
     - 4
     - Payload offset in SPI NOR.
   * - 0x28
     - 4
     - Load address; zero for data-only images.
   * - 0x2c
     - 4
     - Entry address; zero for data-only images.
   * - 0x30
     - 4
     - Load type/attributes.  The RAM stage compares this value with the
       selected boot type; bit-level semantics remain partly inferred.
   * - 0x34
     - 4
     - JAMCRC of the complete aligned payload.
   * - 0x38
     - 4
     - Transformation or parameter subtype.  It is passed to the post-read
       handler by the RAM stage and identifies DDR table variants to the ROM.
   * - 0x3c
     - 4
     - Prefix size.  The RAM stage reads this prefix separately, then loads
       ``stored_size - prefix_size`` bytes from the following flash address.
       It is zero in all currently used FH8626V100 descriptors.

JAMCRC is ``CRC32(payload) XOR 0xffffffff``.  The checksum covers the aligned
size at offset 0x20, including padding.  This is confirmed for the FH8626V100
``param`` and ``uboot`` payloads and all pre-U-Boot payloads in the independent
FH8852V201 sample.  Checksums for the stock kernel and filesystem descriptors
are stale because those partitions were updated after the container was made.

Validated FH8626V100 descriptors
--------------------------------

.. list-table::
   :header-rows: 1

   * - Name
     - Size
     - Stored
     - NOR offset
     - Load/entry
     - Attributes
     - Subtype
   * - param
     - 0
     - 0x0f00
     - 0x001000
     - 0x10000800
     - 0x23
     - 0x1a
   * - uboot
     - 0x2bae4
     - 0x2bb00
     - 0x020000
     - 0xa0800000
     - 0x10
     - 0
   * - kernel
     - 0x2270f0
     - 0x227100
     - 0x050000
     - 0xa0830000
     - 0x70
     - 0
   * - data
     - 0x88
     - 0x100
     - 0x350000
     - 0
     - 0x70
     - 0
   * - res
     - 0x49470
     - 0x49480
     - 0x3d0000
     - 0
     - 0x70
     - 0
   * - app
     - 0x351000
     - 0x351000
     - 0x450000
     - 0
     - 0x70
     - 0

Independent loader-code confirmation
------------------------------------

The FH8852V201 sample has three ``DDR_*`` descriptors, followed by a ``ram``
descriptor and an ``uboot`` descriptor.  Header words 0x0c and 0x10 are 2 and
3 respectively.  Its RAM stage:

* validates ``2BL*`` at header offset 0;
* reads ``(header[0x0c] + header[0x10]) * 0x40`` bytes from flash offset
  0x100;
* walks two descriptors beginning after the three leading DDR descriptors;
* reads descriptor offsets 0x20, 0x24, 0x28, 0x2c, 0x30, 0x34, 0x38 and
  0x3c directly;
* loads the payload from the flash offset to the load address, verifies the
  checksum at 0x34, and returns the entry address at 0x2c;
* retries with bit 0x80 set in the load type after a read/checksum failure.

The code has dedicated paths for load types 0x14 and 0x18.  Type 0x18 is
loaded at ``0xa3000000`` regardless of the descriptor load address.  These
paths are not used by the FH8626V100 production chain and are documented only
to delimit what is known; the checked-in generator preserves the values and
does not attempt to reinterpret them.

ROM parameter table
-------------------

The ``param`` payload is a sequence of 16-byte records followed by zero
records to the descriptor's aligned size::

    struct fh_rom_parameter {
        uint32_t address;
        uint32_t value;
        uint32_t argument_or_delay;
        uint32_t operation;
    };

The board table contains 236 active records and four zero padding records.
Its operation distribution is 228 records of operation 3, four of operation
4, three of operation 5 and one of operation 2.

The interpreter itself is in the FH8626V100 mask ROM, so it cannot be recovered
from SPI NOR.  Cross-comparison of the FH8626 and FH8852 tables nevertheless
establishes the following operational model:

.. list-table::
   :header-rows: 1

   * - Operation
     - Recovered behaviour
     - Third word
   * - 2
     - Poll until ``(read32(address) & argument) == value``.
     - Comparison mask.
   * - 3
     - ``write32(address, value)``.
     - Delay after the operation; zero in all FH8626 direct writes.
   * - 4
     - Set bits: ``write32(address, read32(address) | value)``.
     - Delay after the operation.
   * - 5
     - Clear bits: ``write32(address, read32(address) & ~value)``.
     - Delay after the operation.

Operation 3 accounts for 228 contiguous DDR-controller writes at
``0xed000000``.  The final operation-2 record polls ``0xed0000ec`` for value
0x10 with mask 0xffff.  The set/clear polarity is strongly supported by paired
reset sequences in both SoC samples: operation 5 clears a bit, configuration
is written, and operation 4 sets it again (with the inverse ordering used for
the DDR release sequence).  The delay unit is probably microseconds, but that
unit cannot be proven without mask-ROM code or a timed hardware trace.

All eight non-direct-write records are preserved explicitly:

.. list-table::
   :header-rows: 1

   * - Record
     - Address
     - Value
     - Argument/delay
     - Operation
   * - 0
     - 0xf0000020
     - 0x00008000
     - 0
     - clear bits
   * - 1
     - 0xf000001c
     - 0x00000040
     - 0x64
     - set bits
   * - 2
     - 0xf000001c
     - 0x00000040
     - 0x64
     - clear bits
   * - 231
     - 0xed000000
     - 0x00000001
     - 0
     - set bits
   * - 232
     - 0xed0000ec
     - 0x00000010
     - 0x0000ffff
     - masked poll
   * - 233
     - 0xf0000020
     - 0x00000100
     - 0
     - clear bits
   * - 234
     - 0xf0002024
     - 0xffffffff
     - 0
     - set bits
   * - 235
     - 0xf0002020
     - 0x00070000
     - 0
     - set bits

Records 3 through 230 are the 228 direct DDR-controller writes.  Register
names for the PMU words at 0xf0002020 and 0xf0002024 are not present in the
available FH8626V100 source material, so assigning names to them would be
speculation.

The table's JAMCRC is ``0x5dbc3074``.  Its register values are board- and DDR-
specific even though the record interpreter is common to other Fullhan SoCs.

Remaining bytes
---------------

The range ``0x0e000`` contains a legacy vendor default environment-like block.
Its first word is ``0x0eb9ec57``.  It is not the standard U-Boot environment
CRC32: neither the complete remaining block, the bytes through the double-NUL
terminator, nor tested nearby subranges produce that value or its JAMCRC.
Accordingly the manifest calls it ``unknown_tag`` and preserves it verbatim.
The persistent U-Boot environment is a separate 64 KiB sector at ``0x10000``.
Current mainline U-Boot embeds its own default environment, so the ROM need for
the legacy block is unproven.  It is retained in the manifest for exact binary
reproduction, but it does not add vendor commands to mainline U-Boot.

Generation status and safety
----------------------------

``tools/fh8626_bootchain.py --inspect`` parses the descriptor table, verifies
available payload JAMCRCs and summarizes the parameter operations.  The same
tool can extract the structured manifest from a validated 8 MiB dump and build
the container from that manifest::

    python3 tools/fh8626_bootchain.py \
      --extract-manifest bootrom.json stock-flash-8m.bin
    python3 tools/fh8626_bootchain.py \
      --bootstrap-manifest bootrom.json u-boot.bin output

Manifest format version 2 preserves all descriptor words, all 240 parameter
records (including four trailing zero records), the active-record count, the
unknown legacy tag and the retained strings.  The checked-in manifest therefore
reconstructs all 65536 bytes of the validated stock
container exactly when no replacement payload is supplied.  For release
images, the three confirmed U-Boot descriptor fields are changed once to a
permanent contract: exact size ``0x30000``, aligned size ``0x30000`` and
JAMCRC ``0x251d4c31``.  Each partition reserves its last four bytes for a
calculated CRC correction, allowing different U-Boot binaries to satisfy that
same descriptor without rewriting the bootstrap.

The stock container reconstruction and mainline U-Boot port have separately
passed hardware boot tests.  The fixed-envelope migration path is fully
machine-checked but still requires its first cold-boot hardware validation;
it must not be described as hardware-proven until that test passes.

The validated production binary representation is therefore reproducible,
but this must not be confused with a complete reconstruction of every
bootstrap field or the mask-ROM implementation.
There is no missing executable ``bootstrap`` source for FH8626V100: its first
stage is immutable silicon mask ROM, while the checked-in 64 KiB object is the
fully reconstructed data it consumes.  A source-level reimplementation would
only be possible as an optional replacement preloader and is not required by
the working OpenIPC U-Boot port.

Some mask-ROM semantics remain deliberately labelled as inferred.  Changing
or minimizing the manifest still requires cold-boot tests with a recovery
programmer ready, particularly until the following are established:

* whether the ROM requires product metadata or non-boot descriptors;
* whether the block at 0x0e000 is consulted before U-Boot;
* the exact delay unit and the remaining meanings of descriptor attributes.
