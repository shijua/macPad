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

## Producer-format candidates inspected subsequently

RE-confirmed via the actual bundled arm64 MTLSimDriver:
`-[MTLSimDevice init]+0x224` (image offset `0x2c10`) calls
`setReflectionSerializationVersion:` with 1 or 2 according to the connection
version. The bundled MetalSerializer setter at `0x4544` stores the value at
`self+0x38`. A confirmed consumer at `0x3548` reads it for
`serializeStructType:version:`. This establishes struct-type serialization;
it does **not** establish control over the failing function-reflection payload.
No change to that setting has been deployed.

Runtime-confirmed with an independent native symbol probe, followed by
disassembly of its copied function bytes:
`MTLUseAirntReflection` is at iPadOS Metal+`0x2ec94` and returns 1 after its
once initialization (`+0x1c`). `ShouldCreateAIRVersion` at Metal+`0x13dc8`
also tests that the payload magic differs from `MTLPSBIN`. Sonoma's matching
functions at `0x18a6058f4` and `0x18a592700` implement the same selection.
Thus simply enabling AIR reflection is not a demonstrated fix: this captured
payload is still the legacy binary format.

The read-only probe did not alter any framework, compiler worker, or running
GUI service. Its symbol output and copied-byte disassembly are retained in the
ignored evidence directory. Obtaining genuine AIR reflection upstream, or
deriving a complete translation of the legacy format, remains investigation.
