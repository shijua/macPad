# Weather reflection stream mismatch: diagnostic evidence

Status: the cause of the observed reader overrun is identified; no production
format translation has been shipped. Weather's detailed rendering remains
unverified.

## Runtime evidence

The unchanged Weather reflection payload has 9616 bytes, wrapper version 8,
compiler version 20230418, and a 9534-byte `MTLPSBIN` section at offset 80.
The stream version is `0x20000`.

A diagnostic that calls the original reader unchanged captured:

```text
length=9534 cursor=9526 remaining=8 caller=Metal+0x9f418 next=0x253e
length=9534 cursor=9530 remaining=4 caller=Metal+0x9f424 next=0
length=9534 cursor=9534 remaining=0 caller=Metal+0x9f430 next=0
```

Weather then aborts at the original bounds check. The diagnostic gate
`/tmp/macws_weather_reflection_diag` has been removed from the rootfs;
future launches do not enable it.

## Actual binary comparison

RE-confirmed via Sonoma Metal UUID
`91A4B668-866E-33E2-9812-D5CCFEF34341`:
`MTLInputStageReflectionDeserializer::deserialize` reads five `uint32_t`
fields into object offsets `0xc0..0xd0` for stream versions >= `0x10002`.
The first three return addresses are `Metal+0x9f418`, `+0x9f424`,
and `+0x9f430`. Versions >= `0x20000` subsequently deserialize global bindings.

RE-confirmed via the actual iPadOS 17 Metal implementation, located with
`MSFindSymbol` and copied without changing it:
`MTLInputStageReflectionDeserializer::deserialize` starts at `Metal+0x10e04`.
After the common trailer at `+0x1164`, its version test at `+0x11d8`
directly calls global-binding deserialization at `+0x11f0`. The five macOS
fields do not appear in that function. The actual shared-cache base in this
capture was `0x1b4ff0000`; the captured function address was `0x1b5000e04`.

## Rejected experiment and next requirement

Unwrapping the outer version-8 header did not fix the crash. Sonoma's actual
`MTLNewReflectionData` already recognizes that header and extracts its sections.
That experiment was removed.

The two words remaining at cursor 9526 need to be interpreted using the
producer/global-bindings implementation. Adding zero fields or bypassing the
five reads would hide the protocol mismatch. A fix must derive valid metadata
or adapt the producer/consumer format while preserving the original invariants.

The local ignored evidence directory
`tmp/sonoma-14.0/priority-20261003` contains the reader log and iPadOS function
disassembly. No synthetic pixels or process uptime are used as rendering proof.
