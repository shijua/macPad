# iPadOS 17 startup investigation (2026-09-29)

This is a chronological investigation log. Earlier statuses below describe
the system at that time, including the previous Ventura rootfs. For current
Sonoma results and remaining issues as of 2026-10-02, see the dedicated
[iPadOS 17 + macOS 14 update notes](ipados17-macos14-update.md) and the final
Launchpad ownership section of this log.

Status: USB SSH at `127.0.0.1:2222` works. The package is configured
(`install ok installed`). `run_bash.sh` runs a macOS 13.4 shell and
`sw_vers -productVersion` prints `13.4`. LaunchServices and the other private
macOS service contracts now report ready. The latest coexist-mode startup
still did not reach graphics-ready and restored iOS.

## Observed evidence

The earlier device session reported the Ventura cache pair as:

```
-rwxr-xr-x 1 mobile staff 1.5G May 13 2023 dyld_shared_cache_arm64e
-rwxr-xr-x 1 mobile staff 1.8G May 13 2023 dyld_shared_cache_arm64e.01
```

After signing echo, the runtime reported:

```
dyld cache '(null)' not loaded: syscall to map cache into shared region failed
Library not loaded: /usr/lib/libSystem.B.dylib
```

This proves a cache mapping failure, not its kernel rejection branch. The
claim that iPadOS 17 inherently cannot map Ventura's cache was premature.
The OS cryptex and both cache files already exist; another download is not
currently justified. Extracted dylibs later failed at a non-page-aligned
segment address. That experiment does not prove the original cache is
incompatible with the device.

## Cache ownership: tested on device

Apple's source checks
`va_uid != 0` and returns `EPERM` in
[xnu-10002.1.13/bsd/vm/vm_unix.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-10002.1.13/bsd/vm/vm_unix.c#L2325).
This is source evidence, not disassembly of this device's patched kernel.
The two cache files were owned by UID 501. After changing only their owner
to UID 0, the original dyld cache mapping error disappeared. This is an
on-device before/after result; the precise kernel rejection branch was not
traced.

`macws_prepare_shared_cache.py` validates the existing Ventura pair and
normalizes only its owner. Both installation entry points run it before
their macOS execution steps. It neither registers hashes nor patches code.
Validation includes signature bounds, not cryptographic verification.

The next two failures were distinct. The package post-install script silently
skipped copying `libmachook` when `/usr/local/lib` was absent. Creating the
destination directory exposed a missing `CydiaSubstrate.framework` runtime
inside the chroot. Copying ElleKit into the chroot, patching its Mach-O
platform to macOS 13, signing it, and registering its CDHashes let the
injected `/bin/echo` run. The package now prepares this dependency before
its first chroot process.

The first `/usr/bin/codesign` launched by package configuration was then
`Killed: 9`. After signing that binary with the project's entitlements and
registering its CDHashes, the same launcher ran it and the package advanced
past its codesign seal/verify step. The post-install script now handles this
signature on a fresh rootfs. Stock `/bin/bash` needed the same profile;
the configured package now signs it once, and the regular shell succeeds.
Stock `/usr/bin/defaults` needed the project profile merged with its native
`trust-defaults-kvstore-identifier` entitlement. After the merge, the GUI
startup completed root and uid-501 preferences write/read round-trips.

The first GUI attempt also found a stale `/var/jb/usr` bindfs inode: the
source Dock proxy was executable, but the chroot view retained an older
`0600` inode. Unmounting that one view and remounting it made both paths
resolve to the same executable inode; the bind helper now refreshes that
specific stale mount on future startups.

The first GUI blocker was a separate runtime crash. The device report
`iconservicesagent-2026-09-29-140529.ips` records `EXC_BAD_ACCESS` at
`0x1a`, with the faulting frame in Ventura Core Image (image UUID
`780b768c-4b54-36c3-ac8e-9d6138c86592`, offset `962892`). Its
symbolication names `CI::Perspective::NMSimplex::orderVertices`, but no
claim about the underlying invalid value has been established. The related
`ExcUserFault_iconservicesagent-2026-09-29-140522.ips` records
`XPC_EXIT_REASON_FAULT`. The original `iconservicesagent` binary was extracted
from the exact Ventura IPSW; its UUID is
`C0891064-1633-3883-B091-B90E6490E270`. The return address in that crash
follows its `__qtn_proc_init_with_self` stub call. At runtime, patching the
shared libquarantine function with `MSHookFunction` caused bad-access reports
before the replacement entered, while skipping that patch removed those
bad-access reports. `dyld_dynamic_interpose` did not change the executable's
import slot: diagnostics recorded identical values before and after.

`dyld_info -fixups` on the same UUID confirms that the executable has IA
address-diversified auth-bind imports for `__qtn_proc_apply_to_self` at image
offset `0x8070` and `__qtn_proc_init_with_self` at `0x8088`. The current
hook verifies the UUID and both original import targets, changes only those
two slots, and signs each replacement for its slot address. Runtime log
`iconservicesagent.log` then recorded `qtn self enter`, stock result `-2`
with `errno=103` (`ENOPOLICY`), and the narrow existing quarantine fallback.
The same GUI run reported `Private macOS IconServices endpoints ready`.

### AGX resource creation: earlier failure, now past this stage

The latest device log records the WindowServer's device-info request as:

```
AGXIOC setupImmediate #1 before ... sel=0x100 inSC=0 outSC=120
AGXIOC setupImmediate #1 after outSC=120 result=0
AGX_LIFE CREATE-FAIL id=0 type=0 surf=0 bytes=0x10000 kr=0xe00002be
AGXIOC Method sel=0xa->0x9 inCnt=0 inSC=104 outSC=80 -> 0xe00002be
```

The first selector failure was caused by clamping the 120-byte output size to
112 bytes. A controlled run that kept 120 bytes returned success; the prior
112-byte run returned `0xe00002c2` (`kIOReturnBadArgument`). The compatibility
clamp is now limited to the previously measured iOS build `20D67`; iOS 17
keeps the 120-byte request. The package built and installed with this change.

An earlier 64 KiB heap creation (`sel=0x9`) returned
`0xe00002be` (`kIOReturnNoResources`, per the SDK's `IOKit/IOReturn.h`). A
temporary IOKit probe using a native iOS user-client reproduced the same
result for a zero-filled 0x70-byte request both without `setupImmediate` and
after a successful 0x78-byte `setupImmediate`. This rules out the output-size
fix as the cause of the heap failure, but it does not identify the kernel's
rejection branch.

As a control, a separate native iOS 17 process successfully created an MTL
device (`Apple M1 GPU`) and a 65,536-byte `MTLBuffer`. Later WindowServer
logs also show `ResCreate OK type=0` and `ResCreate OK type=0x82`, and GUI
startup proceeds through Finder, Dock, SystemUIServer and ControlCenter.
Those logs supersede the earlier theory that AGX resource creation is the
current startup blocker.

### Current blocker: Metal shader pipeline version

The current `WindowServer.err` records the first failed SkyLight pipeline:

```
#### RENDER-PIPELINE #1 variant=error device=AGXG13GFamilyDevice ...
vertex=SimpleVertex fragment=UberResampleLanczosFragmentBGRA ...
errorDomain=AGXMetal13_3 errorCode=3
description=Function UberResampleLanczosFragmentBGRA has a deployment target
(0x00020006) which is incompatible with this OS (0x00020005).
```

QuartzCore independently fails on `fixed_frag_lph_cpf` with the same version
pair. The original macOS 13.4 and translated Catalyst metallibs both carry
`VERS` AIR 2.5 for these exact functions (parsed by
`misc/repack_metallib_macabi.py:parse_function_records`). The native iOS 17
QuartzCore metallib carries AIR 2.6. Runtime diagnostic output from the
failing pipeline identifies its specialized fragment object as
`_MTLFunctionInternal` and its `_functionData` ivar as a structure with
`airMajorVersion`/`airMinorVersion` fields. The dumped fields are `air=2.6`
for the failing SkyLight and QuartzCore fragments; the SkyLight base vertex
remains `air=2.5`. This confirms that the version mismatch is present in the
specialized function object after the AIR 2.5 metallib loads. The error values
`0x00020006` and `0x00020005` numerically match AIR 2.6 and AIR 2.5. Their
meaning as deployment-target and OS versions has not been confirmed from the
comparison code, so the earlier interpretation as iOS 16.6 versus 16.5 is
unverified. Changing the field to 2.5 would only suppress validation without
establishing shader compatibility. Translating QuartzCore to Catalyst targets
16.5 and 16.4 both reproduced the failure. The 16.5 profile remains an
experiment, not a fix.

The first `fixed_frag_lph_cpf` specialization trace records `air=2.5,
language=3.0` on the base `_MTLFunctionInternal` and `air=2.6,
language=3.0` on the returned object. The original method's IMP is in the
macOS 13.4 Metal.framework at image offset `+0xf1b00`. Disassembly of that
exact image shows a call at `+0xf1c58` through an Objective-C selector stub;
the selector data in the shared cache resolves to
`newSpecializedFunctionWithDescriptor:destinationArchive:functionCache:sync:completionHandler:`.
This narrows the version change to that specialization operation or its
completion path. The project hooks that asynchronous selector; the runtime
trace identifies the hook in `libmachook.dylib` and its saved original IMP in
macOS Metal.framework at image offset `+0xf10c4`. That original function
calls the specialization machinery at `+0xf1194` (disassembly of the same
Metal image), before returning through the completion handler. It does not
yet identify which component assigns AIR 2.6.

The native iOS 17 `MTLCompilerService` has UUID
`EBA8ED6F-9C82-3F0E-99F2-319A21BB6877`. Its old tweak logged `UUID
mismatch`. Disassembly of that exact 87 KiB executable locates the compiler
request calls at `+0x236c` and `+0x23a4`, and the reply call at `+0x24ec`.
The guarded adapter in `MTLCompilerBypassOSCheck/Tweak.x` now handles those
sites. An independent `PingMTLCompilerService` run logged `target adapter
installed` at both call sites and `compiler reply observer installed` at the
reply site. The WindowServer startup did not produce a compiler request or
reply capture, so this adapter has not been shown to resolve the pipeline
failure. A separate iOS-native Metal source-compilation smoke test did
exercise the new build-request wrapper: it returned a non-nil library, and
the diagnostic log recorded one 478-byte request and a 3,932-byte reply.

The missing `OSXvnc-server` was provisioned from the upstream
[`stweil/OSXvnc`](https://github.com/stweil/OSXvnc) source at commit
`df60d781812b2f36f21fc4037bad66638df3a7c1`, built for arm64/macOS 13
with Xcode 26.3, signed with the project entitlements, and registered in the
device trustcache. The binary runs `-help` inside the chroot. Two bounded GUI
starts then logged `OSXvnc pointer proxy ready at
/var/mnt/rootfs/private/tmp/macws_vnc_pointer_proxy.sock`. This clears the
missing-pointer-proxy startup blocker, but does not validate framebuffer
pixels. Both starts then stopped because WindowServer changed PID during
pointer-proxy startup (`55784` to `55991` in the first run). The launcher
cleaned up and restored iOS.

The restarted WindowServer also logged `RENDER-PIPELINE #1` for
`SimpleColorVertex`/`SimpleColorFragment` with `Internal error during
function compilation`. The iOS-native MTLCompilerService diagnostic log
recorded a 3,712-byte request with discriminator `0x1` for
`SimpleColorFragment`, but no matching reply was observed. Its captured
request contained the translated target triple
`air64-apple-ios19.0.0-macabi`. A controlled SkyLight-only translation to
`air64-apple-ios16.5.0-macabi` converted all 54 functions and passed manifest
verification; the corresponding request changed its triple to 16.5, yet the
same pipeline error and WindowServer PID change recurred. The device's
SkyLight output, manifest, and provisioner were restored to their previous
hashes after this failed experiment. The request alone does not establish
whether the compiler worker crashed, hung, or returned an error by another
path. No VNC pixels or graphics-ready WindowServer have been validated.

The captured 3,712-byte request contains an Apple AIR bitcode module at byte
offset 420. The installed `macws-llvm-dis` disassembled it successfully:
`source_filename = "SimpleColorFragment"`, target triple
`air64-apple-ios19.0.0-macabi`, `!air.version = !{i32 2, i32 5, i32 0}`,
and `!air.language_version = !{"Metal", i32 1, i32 2, i32 0}`. Its function
body returns the input color. This confirms the request contains validly
readable AIR 2.5 bitcode; it does not prove the iOS 17 compiler accepts the
module or explain why no reply appeared in the diagnostic log.

An attempted transfer of the full iOS 17 dyld shared cache was interrupted
and left an incomplete local copy; it was not used for this diagnosis.

### Minimal-pipeline follow-up (2026-09-29)

A fresh chroot probe compiled a trivial `SimpleColorVertex` /
`SimpleColorFragment` source and reached the real `AGXG13GFamilyDevice`
pipeline call. The runtime error was:

```
Function SimpleColorFragment has a deployment target (0x00020006)
which is incompatible with this OS (0x00020005).
```

The `MACWS_PIPELINE_DIAG` function-storage observer reported
`_MTLFunctionInternal air=2.6 language=3.0` for both stages. A follow-up
diagnostic dump captured the complete `MTLFunctionData` type encoding and the
first 128 bytes of each function object. At ivar offset 200, both raw dumps
contain `02 00 06 00 03 00 00 00`, matching AIR 2.6 and Metal language 3.0.
The error's function value `0x00020006` therefore matches the AIR fields in
the failing function objects; the reported OS value `0x00020005` matches AIR
2.5. This runtime evidence strongly identifies the gate as AIR 2.6 versus
AIR 2.5 compatibility, rather than iOS 16.6 versus 16.5. The exact comparison
code has not yet been disassembled, so that interpretation remains an
evidence-backed inference rather than a confirmed field-level comparison.

This separate runtime-confirmed failure blocks a minimal shader, so shader
complexity is not required to reproduce it. The previously captured 3,712-byte
request contains AIR 2.5, but it is not paired with this source compilation's
reply. It therefore does not establish an AIR 2.5-to-2.6 conversion within one
compiler transaction. Do not lower the metadata field alone: that would
suppress the gate without proving the AIR payload is compatible.

A controlled compile-options probe built the same trivial shader with MSL
2.3, 2.4, and 3.0. All three pipeline calls returned the identical
`0x00020006` versus `0x00020005` error. The 2.3 run's function observer
reported `air=2.6 language=2.3`. Lowering the MSL language version therefore
does not lower the AIR compatibility value or unblock this pipeline. The next
useful experiment must change or translate the AIR compiler output itself,
then verify that the real pipeline builds and renders.

### Ventura function-specialization dispatch (2026-09-29)

The exact macOS 13.4 arm64e Metal image was extracted from the local
`UniversalMac_13.4_22F66_Restore.ipsw` shared cache and disassembled with
`ipsw dyld`. The image base is `0x189848000`. RE-confirmed from this image:

- `-[_MTLFunctionInternal newSpecializedFunctionWithDescriptor:destinationArchive:functionCache:sync:completionHandler:]`
  starts at `Metal+0xf10c4` (`0x1899390c4`) and calls the
  `specializedFunctionHash:requestData:constants:specializedName:privateFunctions:completionHandler:`
  selector stub at `0x189a2e060`.
- The synchronous
  `newSpecializedFunctionWithDescriptor:destinationArchive:functionCache:error:`
  entry at `Metal+0xf1b00` calls the async selector stub at
  `Metal+0xf1c58`; it passes `sync=1` and waits for the completion state.
- The async completion block at `0x189939928` calls the demangled
  `processCompiledLibrary(...)` function at `0x189934530`. The follow-on
  completion path at `0x189939f98` calls
  `-[_MTLFunctionInternal initWithName:type:libraryData:functionData:device:]`
  through the selector stub at `0x189a261e0`.

This confirms that the specialized function is rebuilt with `functionData`
after compiler output is processed. It does not yet show which instruction
sets `airMinorVersion` to 6, or whether that value comes from the compiler
reply, an archive parser, or specialization metadata. Do not patch the version
field based on this call chain alone. The next useful capture is the exact
`functionData`/archive bytes entering that initializer, paired with the
compiler reply for the same specialization request.

The Ventura 13.4 Metal cache disassembly also locates the earlier replay
abort in `deserializeArguments` at unslid `Metal+0x8f64`: it masks a decoded
argument-type value to five bits, accepts values 1 through 22, and branches
to the assertion path for other values. The replay's exact rejected value
has not been captured, so this parser range check is evidence about the
failure site, not yet proof of which reply field caused it.

The active tweak, temporary marker files, and probe binary were restored
after each experiment. SpringBoard and backboardd are running again. No
graphics-ready WindowServer, VNC pixels, or desktop have been verified. The
next blocker to resolve is the compiler/runtime deployment-target mismatch;
the number of later fixes remains unknown until that gate passes.

### Source-reply and initializer correlation (2026-09-30)

Runtime-confirmed via `macws-function-data-run-20260930.log`: the diagnostic
initializer observer ran successfully. Both input records already contain
`air=2.6 language=3.0` before the original initializer runs. The minimal
pipeline still returns the same deployment-target error.

The saved 7,512-byte `macws-ios17-source-reply.bin` (SHA-256
`9885738cb290a80c133d23dbcceb1f2502657973e6cd15b7b434ca0b2ebd310c`)
contains an MTLB at offset 104. Parsing its function records with the repo's
`parse_function_records` gives AIR 2.6 / language 3.0 for both functions.
The reply HASH records match the live initializer inputs exactly:

- SimpleColorVertex: `870a05990abe60d3f7db334d18e4d3c1b5fe8a2755894b23104ff79808163f10`
- SimpleColorFragment: `22e8231b778d9961bb5136f0abbfbc0922d1c75f4535d0154d51eadcd9285ea8`

This locates the observed AIR 2.6 metadata in the source-compiler reply,
upstream of function initialization. It does not prove which compiler option
selected that version. The next experiment should pair a fresh, unique source
request with its reply and inspect its target/deployment arguments. The older
AIR 2.5 specialization request must be analyzed as a separate transaction.
All four active hook libraries were restored and their SHA-256 hashes checked
against the pre-experiment baseline. No desktop or rendered pixels are verified.

## Ventura versus Sonoma

Decision updated 2026-09-30: investigate macOS 14.0 next, preserving the
13.4 source image, code changes and runtime evidence as a reconstruction
fallback. The successful iOS-native draw and differing captured command
layouts below justify comparing the newer binaries before investing in a
complete Ventura-to-iOS-17 submission translator. Sonoma compatibility is
still a THEORY; no successful Sonoma runtime test has been performed.

A numerically matching macOS/iPadOS generation is not proof of ABI
compatibility. `libmachook/mac_hooks.m` explicitly targets
13.4 offsets in IOMobileFramebuffer, SkyLight and Metal, alongside many
version-specific layouts. The package also hardcodes two Ventura cache
CDHashes. Swapping to 14 without auditing these would introduce new unknowns.

A Sonoma branch would require the actual 14.x binary UUIDs, disassembly and
validated instruction signatures for each affected patch, dynamic admission
of the real cache hashes, and CLI tests before any GUI tests. No Sonoma image
comparison or successful Sonoma runtime test has been performed here.

### Upstream AIR target and reflection protocol witnesses (2026-09-30)

This section supersedes the earlier statement that selecting AIR 2.5 was
still the first unresolved gate. These are diagnostic experiments; no
production target adapter or general request/reply translator was installed.

**Runtime-confirmed target experiment:** the real iOS 17
`libGPUCompilerImpl.dylib` has UUID
`9e166aee7f46396e81b7b3bba347b9cb`. Its exported
`metalfe::GPUCompiler::getDefaultTargetTriple` is at image offset `0x2e568`.
The temporary wrapper calls the original factory and the actual LLVM
`Triple::setOSName` API, retaining the iOS platform and selecting `ios16.5.0`.
The source reply `reply-67369-001-7512-824bfeda4bd2fb5b.bin` contains AIR 2.5;
its extracted bitcode has target `air64-apple-ios16.5.0-macabi`.
The chroot pipeline passes the earlier deployment gate but returns:

```text
pipeline=0x0 domain=AGXMetal13_3 code=3 error=Internal error during function compilation
```

An iOS-native probe, with its source target selected through the same
factory/API path and explicit Metal language 3.0, produced:

```text
device=Apple M1 GPU
pipeline=0x105814400 domain=nil code=0 error=nil
```

Its source reply is `reply-67454-001-7480-1dec8868ac0a30f9.bin` and fragment
request is `raw-67454-002-1-3432-97d044f379109e03.bin`. This confirms a minimal
native pipeline, not a rendered frame or a working chroot pipeline.

**Runtime-confirmed reflection rejection:** replaying that exact successful
native fragment request into the chroot transaction produced a 2,624-byte
reply (`reply-67505-001-2624-185580e2f72842f7.bin`). A process-private BRK
at the old Metal abort call captured the real rejected value and stopped
the probe; it did not allow the failed check to continue:

```text
REFLECTION-REJECT-TRAP image=/System/Library/Frameworks/Metal.framework/Versions/A/Metal base=0x1a06f4000 site=0x1a0784494 instruction=9402ccab protect=0
rawType=0x50000000 maskedType=0
```

The saved 512-byte payload (`macws-reflection-rejected.bin`) matches the
compiler reply at byte 24. Its header has `0xef13c710` at byte 0,
`MTLPSBIN` at byte `0x50`, and `AIRR` at byte `0x84`. The captured
DeserialContext cursor is byte 25. RE-confirmed via the actual Ventura
Metal cache: `DeserialContext::deserializeUint32` at unslid `0x18986c0e0`
reads the byte pointer, size and cursor from context offsets 0, 8 and 16;
`deserializeArguments` rejects masked argument types outside 1..22.
The fragment reader at `0x1898d8ebc` checks for `MTLPSBIN` at the start,
so simply forwarding this newer wrapped payload is not compatible with
that entry point. A complete reply translator or a supported older-format
compiler output remains to be established. Skipping the check is not a fix.

**RE-confirmed request version gate:** actual iOS 17 `MTLCompiler` UUID
`4567bc2bb425367bb3c1685cd6b026a6`, runtime image base `0x1f41bd000`:

```text
1f41e4d44 ldr x8, [x21, #0x20]
1f41e4d4c ldr w25, [x8, #0xc0]
1f41e4d50 cmp w25, #0
1f41e4d54 mov w9, #0x7d17
1f41e4d58 ccmp w25, w9, #4, ne
1f41e4d5c cset w27, ne
1f41e4f24 and w9, w9, #0x200000
1f41e4f28 orr w9, w9, w27
1f41e4f30 cmp w9, #0
1f41e4f3c mov x2, x25
1f41e4f4c bl #0x1f41e5128
```

Here `0x7d17` is 32023. The 3,440-byte chroot request has 31001 at
`0xc0`; the 3,432-byte native request has 0 there. Changing only the
native request's bit 31 to match the old request still returns the newer
payload and fails the same reader. Adding 31001 to that otherwise successful
native request instead returns the real service error:

```text
compiler error reply request=1 discriminator=0x1 code=2
compiler error message request=1 text=Internal error during function compilation
```

Logs are saved as `macws-client-version-trial-syslog.txt`. The exact meaning
of the downstream alternate compiler path remains under investigation;
these observations do not justify globally rewriting arbitrary versions.
All experiments restore the baseline tweak, diagnostic marker and isolated
function cache. Desktop/VNC pixels remain unverified.

### Minimal AGX pipeline passes; execution remains blocked (2026-09-30)

Runtime-confirmed via `macws-original-zero-version-trial-syslog.txt`:
changing only `0xc0` from 31001 to 0 in the original 3,440-byte test
request makes the actual compiler return data. The unmodified downstream
reader then rejects the newer wrapped reflection payload as above.

RE-confirmed follow-up: `MTLCompiler+0xa588c` maps 31001 to 5 and 32023
to 6, then calls the real `MTLWriteAIRBitcodeToMemoryBuffer` export in
`libGPUCompiler.dylib` (`+0x6cbc`, runtime `0x1f4486cbc`). This is AIR
bitcode serialization, not evidence of loading another compiler binary.
Do not infer a replacement compiler installation from this version gate.

A second **diagnostic** in the macOS probe forwards the wrapper's actual
MTLPSBIN subrange into the original
`-[MTLFunctionReflectionInternal initWithDevice:reflectionData:functionType:options:]`.
It validates method encoding `@48@0:8@16@24Q32Q40`, wrapper magic,
section bounds and section magic before selecting the subrange. It does
not fabricate reflection, bypass assertions, or replace the original
reader. Combined with the test-request version normalization:

```text
DIAGNOSTIC-REFLECTION-SECTION type=2 full=512 offset=80 size=44
DIAGNOSTIC-REFLECTION-SECTION type=1 full=736 offset=80 size=266
pipeline=0x13c023c00 domain=nil code=0 error=nil
```

Runtime-confirmed via `macws-reflection-section-trial.log`: both stages
of the minimal chroot pipeline now pass the actual old reflection reader.
This result is limited to the SimpleColor shader and does not validate
resource argument reflection for arbitrary programs. The source cache
already contains the earlier AIR 2.5 factory experiment; a clean-source
production path has not been installed or verified.

The next probe really allocates two render targets and a command queue,
encodes a three-vertex draw, commits it and waits for completion. It does
not claim success from the pipeline object alone. Runtime-confirmed via
`macws-gpu-triangle-submit-run.log`:

```text
GPU-WITNESS deviceClass=AGXG13GFamilyDevice pipelineClass=AGXG13GFamilyRenderPipeline
GPU-WITNESS texture=0x12e942000 auxiliary=0x12e943280 queue=0x13e027600
GPU-WITNESS status=5 error=Internal Error (00000100:Internal Error)
GPU-WITNESS errorUserInfo={
    MTLCommandBufferEncoderInfoErrorKey =     (
        "<errorState: MTLCommandEncoderErrorStateCompleted, label: macws-triangle-encoder, debugSignposts: (null)>"
    );
    NSLocalizedDescription = "Internal Error (00000100:Internal Error)";
}
```

The paired USB syslog `macws-gpu-triangle-submit-syslog.txt` records:

```text
macws-reflection-reject-trap(Metal)[68025] <Error>: Execution of the command buffer was aborted due to an error during execution. <private>
```

This establishes an execution failure; it does not identify its kernel
rejection point or prove that generated machine code is incompatible.
The kernel/GPU submission boundary and command-buffer completion metadata
need their own runtime or RE witnesses. No rendered triangle, VNC pixels,
WindowServer desktop or blur have been verified. Temporary compiler tweaks,
diagnostic markers and the isolated function cache are restored by the
trial's cleanup trap.

### Native pixels and iOS 17 submission boundary (2026-09-30)

Runtime-confirmed via `macws-native-render-triangle-signed-run.log`:
the iOS-native probe, signed with the same project entitlement plist as
the chroot probe, executes the draw successfully from SSH:

```text
GPU-WITNESS deviceClass=AGXG13GDevice pipelineClass=AGXG13GFamilyRenderPipeline
GPU-WITNESS status=4 error=nil
GPU-WITNESS matchingPixels=496/1024 expectedBGRA=106,49,188,255
```

The first native attempt used plain ad-hoc signing and returned `device=nil`;
that is not a valid platform comparison. The matching-entitlement run above
is the comparison witness. The macOS run with both render-target load
operations changed to DontCare still returned status 5, and a diagnostic
readback after that error found `matchingPixels=0/1024`. Thus the failure
is not restricted to the clear load action, and no drawn pixels have been
observed in the chroot.

The macOS submit recorder captures exactly one command. Its existing
adapter reports:

```text
AGX_SUBMIT_DIAG #1 TEMP-KCMD-ABI-FIX subtype1-clear pads=0x1c0,0x4c0 total=0x858->0x838 size=0x7e8->0x7c8 end=0x818->0x7f8 segment-span=0x838
AGXIOC Method sel=0x1e->0x1a inCnt=4 inSC=56 outSC=0 -> 0x0
IOGPU-ERROR-GETTER observation=1 commandBuffer=0x158f3e2f0 class=AGXG13GFamilyCommandBuffer submitSerial=1 fixed=1 domain=MTLCommandBufferErrorDomain code=1 description=Internal Error (00000100:Internal Error)
```

Runtime-confirmed via `macws-native-kcmd-boundary-run.log`: a read-only
wrapper on the actual native `IOGPUCommandQueueSubmitCommandBuffers`
captures the same draw at the native submission boundary. The method
`getCurrentKernelCommandBufferStart:current:end:` is called only after
checking its real encoding `v40@0:8^^v16^^v24^^v32`. Native storage ivar
`_storage` is obtained from the actual class metadata (offset `0x1f0`),
not guessed from the macOS object:

```text
NATIVE-QUEUE-SUBMIT flags=0 count=1 stride=56 queue=0x100a22010
NATIVE-QUEUE-KCMD start=0x1007f0000 current=0x1007f0868 end=0x1007f4000 length=868
NATIVE-QUEUE-SUBMIT return=0
GPU-WITNESS status=4 error=nil
GPU-WITNESS matchingPixels=496/1024 expectedBGRA=106,49,188,255
```

The native capture is 0x868 bytes; the macOS capture is 0x858 before and
0x838 after translation. There are also concrete header-position differences:

| Offset | Native iOS 17 | macOS 13.4 before translation |
| --- | --- | --- |
| 0x18 | 0x30 | 0 |
| 0x1c | 0x808 | 0 |
| 0x20 | 1 | 0 |
| 0x24 | 0 | 0x30 |
| 0x28 | low word of GPU address | 0x818 |
| 0x2c | high word of GPU address | 0x7e8 |
| 0x34 | 0 | 1 |

These are byte observations, not a complete field schema. A length-only
padding patch would not account for them. THEORY: the existing converter
still emits the older submission layout expected by its iOS 16 reference.
Confirm the header/body schema against the actual native writer and kernel
parser before installing an iOS 17 converter. Do not copy a captured native
command containing another process's resource addresses into the chroot.

RE-confirmed via actual iOS 17 IOGPU UUID
`2ea934dd416b3e23a09ed582968d5bf6`, exported submit at `+0x4e90`:
the one-command / stride-at-most-0x40 case takes the small-submit branch
at runtime `0x22ab57f14..0x22ab57f30`. The larger-case branch at
`0x22ab57f40..0x22ab57f78` uses selector 0x1a and four scalar arguments.
This explains why observing IOConnectCallMethod alone missed the successful
native draw; it does not prove that using that alternate submission entry
will repair macOS command bytes.

Evidence copies, temporary diagnostic sources and trial scripts are saved in
`tmp/ipados17-metal-20260930/` (ignored by Git). Temporary source changes
remain diagnostics. The only repo document changed in this continuation is
this investigation file; existing production source edits are retained.

### Sonoma image and submission audit (2026-10-01)

The Apple CDN image `UniversalMac_14.0_23A344_Restore.ipsw` is downloaded.
All ZIP entry CRCs and the embedded BuildManifest version/build passed.
Size: 13,905,898,651 bytes. SHA-256:
`c5a137b905a3f9fc4fb7bba16abfa625c9119154f93759f571aa1c915d3d9664`.
Validation record: `tmp/sonoma-14.0/validated-image.json`.
The transition backup SHA-256 manifest was also verified in full.

Actual cache images: Metal 341.16.1 UUID
`91A4B668-866E-33E2-9812-D5CCFEF34341`; IOGPU 93.0.0 UUID
`F715E9B3-5DFB-3995-BA08-548336E8F140`; AGXMetal13_3 275.6.1.2 UUID
`3D006BBC-4356-36A3-993F-5067CF3CC690`.

RE-confirmed via that IOGPU image at `+0x16bec`: the exported
`_IOGPUCommandQueueSubmitCommandBuffers` uses the same five argument
registers and small-submission conditions as the captured iOS 17 function:

```
0x19eb3dc68: cmp w24, #1
0x19eb3dc6c: b.ne #0x19eb3dc9c
0x19eb3dc70: cmp x22, #0x40
0x19eb3dc74: b.hi #0x19eb3dc9c
0x19eb3dc7c: ldr w0, [x8, #0x14]
0x19eb3dc80: mov w1, #0
0x19eb3dc84: mov x3, x22
0x19eb3dc88: mov x4, x20
0x19eb3dc8c: bl #0x19eb46a48
```

The larger macOS path uses selector `0x1e` at `0x19eb3dcc0`; the actual
native iOS 17 path uses `0x1a` at `0x22ab57f64`. Raw exports, function
bytes and disassembly are under `tmp/sonoma-14.0/iogpu-*`. This comparison
supports testing Sonoma; it does NOT establish command-packet compatibility,
shader compatibility or successful GPU execution.

Filesystem staging is incomplete. The unprivileged initial rsync exited 23,
including an actual `usr/sbin/visudo` read-permission failure and unreadable
Data-template database directories. The administrator retry returned macOS
error -60005. The reviewed preparation script is
`/private/tmp/macws-prepare-sonoma.sh`, also saved at
`tmp/sonoma-14.0/prepare-sonoma.sh`; `bash -n` passes. It assembles the system,
Data template and Cryptex files, excludes x86/AOT caches, and creates the
Data/cache links. Completion only means filesystem assembly; no startup
patch or device execution is implied.

USB SSH returned `Connection reset by 127.0.0.1 port 2222`. No iPad rootfs
files were deleted or replaced. Device migration still requires complete
staging, actual 14.0 binary adaptation, a fresh device-data backup and safe
unmounting of every old rootfs nested mount. The old Mac staging rootfs was
already deleted in the preceding turn; the original 13.4 IPSW and verified
transition backups remain available.


### 2026-10-01: filesystem assembly and USB CLI preflight

The administrator assembly subsequently completed at
`/private/tmp/macws-sonoma-14.0/rootfs`; the completion marker and 14.0
SystemVersion were checked. `tmp/sonoma-14.0/rootfs` points to this stage.
USB root SSH on 127.0.0.1:2222 is available again.

Runtime-confirmed via `tmp/sonoma-14.0/raw-cli-diagnostic.log`:
```text
dyld[68639]: <90E5A160-D906-31EE-950B-E08C34D4F136> /bin/echo
dyld[68639]: <F0A54B2D-8751-35F1-A3CF-F1A02F842211> /usr/lib/libSystem.B.dylib
diagnostic-exit=133
Trace/BPT trap: 5
```
The separate `/var/mnt/macws14-preflight` contains signed dyld/echo and
Sonoma caches with their actual CodeDirectories admitted. No hook is inserted
in this raw test. Trap PC is still unknown; older September 29 echo crash
reports have Ventura UUIDs and cannot explain this result. Debugserver is
being installed to obtain registers and actual faulting instructions.
The old device rootfs remains intact, including its nested mounts.


Hardware-breakpoint LLDB resolved the raw trap (runtime-confirmed via
`tmp/sonoma-14.0/lldb-raw-cli-hardware.log`):
```text
stop reason = EXC_BREAKPOINT (code=1, subcode=0x18a00ff18)
0x18a00ff10: add x0, x0, #0xd53 ; "os_variant had unexpected status"
0x18a00ff18: brk #0x1
```
A software-breakpoint run changed a dyld code page to rw- and stopped at an
earlier execution-access fault. Use `target.require-hardware-breakpoint true`
on this device; do not attribute that debugger-induced fault to raw startup.

The installed thin libmachook plus launchdchrootexec, with
MACWS_UTILITY_PROCESS=1, passes Sonoma echo/bash/child echo (exit 0).
`hook-shell-codesign-test.log` also records codesign starting, but reporting
`/bin/echo: no signature`; this is NOT signature-validation success.

The native mount_bindfs command at `/var/jb/usr/bin/mount_bindfs` is an
auto-bindfs wrapper accepting separate PATH arguments; it is NOT the
two-path mount tool expected by older instructions. Its unintended mounts
were removed; the old rootfs /var/jb/usr mount restored with the actual
`/var/jb/usr/libexec/mount_bindfs/jbctl-bindfs -m SOURCE TARGET`. Verified
unmounted duplicate caches beneath procursus/bindfs were removed, including
the copied usr tree (three key hashes matched the original before removal).
New diagnostic mounts are mini private/tmp from old private/tmp and mini
private/var/jb/usr from /var/jb/usr. These MUST be unmounted before old rootfs
removal. The same autosignd socket inode connects at its native path but
returns ECONNREFUSED through bindfs (native Python connection witness);
manual native jbctl proc_set_debugged at the debugger exec stop is used
solely for the Metal diagnostic, preserving EnableJIT's invariant.

`lldb-metal-authorized.log` reports missing libobjc-trampolines. Stock14
trampoline has x86_64/x86_64h/arm64e; the existing architecture provisioner
appended ARM64/ALL in the mini root, then signed and admitted it.
`lldb-metal-trampolines.log` advances to:
```text
device=Apple M1
library=0x0 error=This library format is not supported on this platform (or was built with an old version of the tools)
Process 68911 exited with status = 3
```
Sonoma SkyLight contains 29 functions; its standalone diagnostic translation
with the existing 16.5 macabi experimental target converted all29 without
AIR lowerings. This does not validate the target or justify shipping that
profile: runtime library/pipeline admission remains to be tested.


### Sonoma resource ABI and first real GPU pixels

Runtime-confirmed `lldb-upstream-buffer.log`: AGXBuffer class is present but
a normal4096-byte buffer returns nil. `lldb-buffer-iokit.log` records the
parent resource request returning e00002c2; `lldb-buffer-native-signed.log`
records native iOS17 successfully accepting the same104-byte request layout,
with different process VA/resource ID values. The unsigned native probe
reported no device; its project-entitled repeat obtained the real device
and allocated4096 bytes. This is a control, not a new entitlement hypothesis.

`lldb-raw-resource-trial-fixed.log` is the successful isolation experiment:
CydiaSubstrate MSFindSymbol located the actual IOKit export, and only
104-byte resource creation requests were dispatched with selector9 and
unchanged arguments (macOS caller selector a). Its output:
```text
GPU-WITNESS status=4 error=nil
GPU-WITNESS matchingPixels=496/1024 expectedBGRA=106,49,188,255
Process 69119 exited with status = 0 (0x00000000)
```
The initial raw trial accidentally used the prior binary because compilation
failed on a missing dyld header. It is NOT evidence for the direct-call test.
The fixed trial rebuilt successfully before transfer.

The renderer uses the actual Sonoma SimpleColorVertex AIR ABI:
attribute0=float4 color, attribute1=float2 position, buffer1=float4x4 MVP,
with three real vertex records and an identity matrix. Saved original module
and LLVM disassembly: `SimpleColorVertex.bc/.ll`; source target macOS14.0,
AIR2.6, Apple metal32023.34. No fabricated pixels or constant-return
resource substitutes are involved in this witness.

Production source now preserves the native wire request only for IOGPU
F715E9B3-5DFB-3995-BA08-548336E8F140, actual kernel21A329, translated
selector9 and request size104. Exact guard tests and startup/cache checks
passed19 tests. Building libmachook and testing without the raw-call
diagnostic are still required. Desktop/WindowServer remains unverified.


Production fix verification: `lldb-production-resource-fix.log`, built from
the current repository libmachook and ordinary renderer without IOKit tracing
or raw dispatch overrides:
```text
GPU-WITNESS upstreamBuffer=0x11f90cec0 class=AGXG13GFamilyBuffer
GPU-WITNESS texture=0x11e610c60 auxiliary=0x11e6127d0 queue=0x11e808800
GPU-WITNESS status=4 error=nil
GPU-WITNESS matchingPixels=496/1024 expectedBGRA=106,49,188,255
Process 69150 exited with status = 0 (0x00000000)
```
The same new ARM64/E library passes bash and a child echo. Thin variants were
platform-tagged for macOS, signed twice on-device, and their CodeDirectories
admitted. Only the separate preflight root's libraries were replaced; the
installed iOS-side copies and old full13.4 rootfs remain baseline.

Next: adapt full14.0 rootfs startup services and strict13.4 shader provisioning
checks. The shipped launchservicesd payload is a converted13.4 ARM64/E Mach-O:
MH_DYLIB, PIE cleared, an LC_ID_DYLIB added, and PAGEZERO reduced to the16KiB
before TEXT. Sonoma stock launchservicesd is ARM64/E MH_EXECUTE with LC_MAIN
entryoff217956,28 commands/3608 bytes; it must be converted from its actual
14.0 original rather than copying the old payload. Keep LC_MAIN so the current
loader reads the original entry offset. No full device rootfs deletion or
WindowServer launch is yet justified by a desktop witness.

### Sonoma startup payload and shader closure (2026-10-01)

RE-confirmed from the actual 23A344 launchservicesd ARM64/E slice:
UUID 57514207-F477-361C-A969-D82EFD96AB5B, LC_MAIN entryoff217956,
load commands end3640, first section file offset6628; intervening bytes are
zero. The stock file is universal x86_64/arm64e (otool reports each slice).
`prepare_launchservices_payload.py` requires the actual UUID, validates all
command bounds and available padding, and applies the existing loader's
MH_DYLIB/LC_ID_DYLIB/PAGEZERO contract. Instructions, section offsets and entry
are preserved. The output needs fresh signing. Device witness
`tmp/sonoma-14.0/launchservices-payload-probe.log`:
```text
[launchdchrootexec] target=/bin/launchservices-payload-probe arch=arm64 insert=/usr/local/lib/libmachook_arm64.dylib
PAYLOAD-DLOPEN admitted
```
This tests loading, not the service's main loop or endpoint readiness.

Actual Sonoma QuartzCore is a three-slice universal archive: AIR cpu01000017
subtype10 offset72 size1265776, GPU slices subtype322 and402. Whole-source
SHA256 is e9284537b6703522149dee9df5609fc2c9d77e365853fb5e1c0563e66e89a33a.
Passing the universal file directly to the old translator failed with
`ValueError: input is not an MTLB container` in quartzcore-translation14.log.
The production translator now extracts the sole validated AIR slice and
retains the whole universal source identity for runtime route validation.
Bounds, alignment, overlap, duplicate AIR and unsupported AIR subtypes fail
closed. The new sonoma14-ios165-macabi profile names the actual source family.

Runtime-confirmed library/function admission on real Apple M1:
```text
# lldb-quartzcore-library14.log
SHADER-LIBRARY 0x1386139d0 error=nil
SHADER-FUNCTIONS admitted=150 failed=0
# lldb-mpsimage-library14.log
SHADER-LIBRARY 0x127946f80 error=nil
SHADER-FUNCTIONS admitted=1831 failed=0
```
Both probes exit0. They run under debugger with native proc_set_debugged at
exec, as did the earlier real SkyLight draw witness; full normal service JIT
and compositor coverage still need validation. Function admission is not a
claim that every compute/render pipeline has executed successfully.

`ensure_sonoma_shaders.py` pins all three actual source hashes and validates
the full closure before writing outputs. It accepts only macOS14.0/23A344
with kernel21A329 and writes complete translated companions and manifests.
postinst selects it for14.0; the existing Ventura source checks remain.
40 focused tests and shell syntax checks passed. The19 backup manifest
entries were rehashed successfully before any destructive migration action.
Old device rootfs is still mounted and preserved; no new deletion this turn.

### Full Sonoma deployment and display ABI evidence

The administrator overlay merge completed, and its31 file hashes were
verified from the protected Mac staging root. Immediately before replacement,
all23 backup manifest entries were rehashed, including fresh installed
runtime/configuration/user data and the separate private/var/root archive.
The project cleanup script stopped the old GUI stack and restored iOS.
Both old nested mounts were unmounted. Device deletion used fd-safe rmtree,
required an actual13.4 physical directory, rejected every remaining nested
mount, and checked that native sh/jbctl/python resolved outside its target.
Runtime witness `old-rootfs-removal.log`:
```text
CHECKED: macOS13.4 directory; zero mounts; native tools outside target
DELETED: /private/var/mnt/rootfs (old13.4); empty target recreated
```
Available device space rose to28GiB. Original13.4 IPSW and backup archives
remain on the Mac. A privileged Mac tar producer streams the new rootfs over
USB through a user-owned FIFO; no complete tar archive is written to disk.
Completion, destination hashes, CLI and desktop remain separate witnesses.

RE-confirmed actual23A344 IOMobileFramebuffer UUID
38690B38-1FAA-3211-89D2-1A8A2D0424EB, image base0x18be9b000:
`iomfb14-swapend-disasm.txt` has `mov w3,#0x4fc` at0x18bea082c,
`iomfb14-swapbegin-disasm.txt` stores swapID with
`str w8,[x19,#0xb0]` at0x18bea07c8. Its public SwapEnd wrapper loads its
dispatch slot at framebuffer+0x868. SwapCancel sends scalar selector0x34
with one input. The native read-only `iomfb_userspace_dump.c` was compiled
for this device and did not submit or cancel any frame. Its runtime bytes,
decoded in `iomfb-native17-kern-disasm.txt`, confirm:
```text
0x1e579fb1c: 819f8052 mov w1, #0x4fc
0x1e579fb3c: 68b200b9 str w8, [x19, #0xb0]
0x1e579ed9c: 839f8052 mov w3, #0x4fc
0x1e57a3824: 81068052 mov w1, #0x34
```
The native public SwapEnd dispatch also uses slot0x868. This confirms these
specific protocol fields match14.0 and17.0, not that every display path works.
The existing13.4 coexist adapter uses size0x46c, swapID+0x68 and slot0x728;
it cannot be transferred to14 by changing one address. Its legacy image
offset checks do not match the actual14 extracted image. QuartzCore's
cancel-completion observer is also guarded by a13.4 UUID. Full compositor
and display coexist support remain unverified; no assertion bypass or
fabricated pixels count as acceptance.


### Full Sonoma deployment and GUI admission (2026-10-02)

Runtime-confirmed via `full-rootfs-cli.log` and
`full-rootfs-gpu-witness.log`: the full 14.0 rootfs now runs bash, child echo,
and a normal autosignd/JIT AGX draw without a debugger. The command completed
with status 4 and 496/1024 matching pixels. This is a GPU draw witness, not a
desktop witness. Destination verification checked 12 critical files and 31
overlay files against their manifests.

The user explicitly authorized continuing despite thermal pressure. The
session environment `MACWS_ALLOW_THERMAL_PRESSURE=1` keeps sensor validation
and logging, admits the shell trust gate, and omits the scanner thermal tool
for that invocation. Default behavior remains unchanged. Runtime-confirmed
via `full-rootfs-gui-trust-override.log`: 1819 files scanned, 74 missing hashes
added and live membership verified.

The first GUI attempt still called the Ventura shader provisioner and failed
with `[ERROR] QuartzCore default.metallib is not the supported macOS 13.4
library.` GUI preflight now selects the Sonoma provisioner using the actual
SystemVersion.plist; the provisioner checks 14.0/23A344, 21A329 and the complete
source hash closure before accepting any companion.

Runtime-confirmed via `systemstatusd-sign-admission.log`: stock systemstatusd
was terminated with exit 137; after project signing and actual CDHash
registration, launchd started PID 78593. This experiment establishes admission
for this binary; it does not identify the precise kernel rejection site.
`defaults` subsequently received `Killed: 9` before the preferences write.
It was project-signed and registered, and the private cfprefsd copy was rebuilt
from the current Sonoma stock binary with its dedicated entitlement profile.
The next GUI startup is testing actual persistent preferences round-trips.
Desktop output remains unverified.


Root and uid-501 CFPreferences write/read now pass. The restored mobile probe
plist was root:wheel/0600; its containing folders already had uid501. Restoring
that file owner to501 admitted the real round-trip. Fourteen stock GUI service
images were audited/signed with the existing project profile and actual hashes
registered; original stock files remain in the validated Mac rootfs/IPSW.

RE-confirmed via `iconservicesagent14-disasm.txt`: the 23A344 arm64e executable
UUID F867B5E6-9611-31AD-97ED-65AAECC9E0D9 checks quarantine setup at
+0x2b98..+0x2c34 and sets flags6. `dyld_info -fixups` places init_with_self at
+0x8090 and apply_to_self at+0x8078 (IA, address-diversified, discriminator0).
Runtime-confirmed via `quarantine-sonoma-runtime.log`: self initialization and
apply return -2/errno103; empty initialization and setting flags6 succeed.
The existing narrowly scoped compatibility profile was extended to these
actual UUID/import slots. Cross-build passes. This is **not yet a fix**:
`iconservices-sonoma-diagnostic.log` proves the UUID matches but the import
page writable-protection request returns2. The VM_PROT_COPY experiment also
returns2 in `iconservices-sonoma-cow-diagnostic.log`. The agent still exits1.
Next evidence must inspect this mapped region's current/max protection and
mapping provenance; do not bypass the agent startup check or synthesize its
service result. Desktop remains unverified.


### IconServices private import mapping and library controls (2026-10-02)

Runtime-confirmed via `iconservices-sonoma-mapping-diagnostic.log`: the
verified Sonoma import page is private, 16 KiB, current protection1 and
maximum protection3. Both direct protection and VM_PROT_COPY return2.
Pre-exec debugger authorization did not change that result. A function-entry
trampoline experiment was removed after a separate ImageIO/malloc abort;
that failure does not establish a precise trampoline root cause.

The current Sonoma-only adapter copies that complete verified page into
an anonymous mapping, edits only the two PAC-signed quarantine imports for
their final addresses, and remaps the page read-only at the original address.
Runtime-confirmed via `iconservices-sonoma-remap.log`: remap result0, native
self-init -2/errno103, then stock ENOATTR fallback and flags6 admission.
The adapter contract test preserves other native results and errors.
This proves startup admission past quarantine, not a completed icon request.

Runtime-confirmed via `gpu-baseline-arm64-control.log`: restoring the
hash-verified startup-overlay arm64 library restores the normal AGX render:
`GPU-WITNESS status=4 error=nil` and
`GPU-WITNESS matchingPixels=496/1024 expectedBGRA=106,49,188,255`.
The rebuilt arm64 library had no completed draw. Its regression cause remains
THEORY; both binaries are preserved for comparison.

Catalog seed still times out and the real workspace icon request aborts with
134 (`catalog-baseline-arm64-control.log`). Several providers record exit9;
that signal alone does not identify a code-signing or protocol rejection.
An initial two-library control is INVALID: cleanup had stopped autosignd,
and `catalog-baseline-both-control.log` explicitly records connect_errno61
and the isJITEnabled assertion. It must not be used to attribute failure
to a library. The control was repeated with autosignd RPC verified.
Desktop remains unverified.


### CoreServices map destination and real catalog witnesses (2026-10-02)

Runtime-confirmed via `coreservices-lldb-guard-excerpt.log`: normal launchd
coreservicesd reached the main/server threads and then raised EXC_GUARD
(code2305843022098595840) in libmachook image+0xf660 while sending MWCM.
The SDK mach/port.h identifies reason3 as INVALID_OPTIONS. The native port
probe (`coreservices-target-port-kind.log`) queried the exact paused task:
`port=0x3e03 kernel_object kr=0 kind=2`. The bridge had intercepted every
foreign-task mapping and sent its userspace IPC to this kernel object.

`macws_core_services_is_map_bridge_port` now queries the destination: kernel
objects and failed/unavailable queries retain the original mach_vm_map call.
Only ordinary userspace ports enter the existing mapping bridge. No mapping
result or catalog contents are synthesized. The actual admission function is
compiled/tested for ordinary ports, kernel ports, query failures and absent
API. Cross-build passes and 61 targeted tests pass. The new arm64e library
is deployed; the verified startup-overlay arm64 library remains installed.

The next real client sample (`lsregister-constructor-hang.log`) was already
in a synchronous Foundation/XPC request, not a hook constructor. lsd's sample
(`lsd-request-wait.log`) awaited CarbonCore's actual SCSessionUniverse request.
The missing provider csnameddatad had exit137 even in a standalone admission
control (`csnameddata-stock-admission.log`). Project signing on a new inode
and registering the resulting CDHash admitted the unchanged binary code.
Its original signed image is preserved as `csnameddatad-stock-23A344`.

Runtime-confirmed via `catalog-after-csnameddata-sign.log`:
`seed-exit=0`
`file-icon-ready path=/System/Applications/Utilities/Terminal.app output=/tmp/sonoma-terminal-icon.png points=32x32 pixels=1024x1024 bytes=71802 representations=32`
`icon-exit=0`
The separate `catalog-live-record-verification.log` verifies Terminal,
Finder, Dock, System Settings and all49 actual Settings extension records:
`settings-extensions-verified candidates=49 records=49` and `verify-exit=0`.
These are completed catalog/icon requests, not a WindowServer desktop.

PluginKit pkd still has exit9 before a suspended-entry witness. Removing
only daemon-container, removing only system-container, registering every
existing CodeDirectory, changing only the path, and extracting the unchanged
arm64e slice did not admit it. The original image/entitlements were restored.
All executable page hashes and embedded entitlement/requirement blob hashes
verified locally; these checks do not identify the kernel rejection site.
Do not repeat these controls as speculative fixes. Native logging is being
prepared to capture the actual exec refusal.

RE-confirmed via `quartzcore14-frame-info-disasm.txt`: QuartzCore UUID
DCE2EDB3-C713-39F9-8AF6-3102F2B9B695, base0x18858c000; enable-tag-list
image+0x2c0c90 reads server+0x58 then display+0x6328 for the framebuffer.
Callback is image+0x2c00d8. The old framebuffer offset+0x300 is incompatible.
Remaining display flag/vector fields, callback timing/fence and pre-lock
pacing must be derived before activating the Sonoma coexist path.


### Sonoma display profiles and service admission (2026-10-02, continued)

The previous pkd blocker above is resolved. Runtime-confirmed via
`tmp/sonoma-14.0/pkd-native-log-probe-v17-re.log`:
`Sandbox: hook..execve() killing pkd.macws-sign-new[pid=82297, uid=0]: (err=2) failed to set executable path`.
Removing only `seatbelt-profiles` admitted the executable. Registering the
stock FAT PlugInKitDaemon framework's actual hashes then admitted that
unchanged dependency. `pkd-stock-framework-trust-control.log` records
`com.apple.systempreferences.GeneralSettings(1.0)` and
`private-pkd-query-exit=0`: a real private PluginKit request completed.
`pluginkit` itself needed the existing project signature and live trust.
No daemon's protocol responses were synthesized.

Native logging is readable after correcting this iPadOS17 stream layout:
entry union at +0x38, message format/buffer/length at +0x58/+0x60/+0x68.
RE-confirmed via `native-log-formatter-disasm.txt`, and runtime-confirmed
via the native probe logs. The opaque inserted words have no inferred
meaning. Sources and probe remain under tmp as diagnostics.

RE-confirmed against the actual 23A344 images: the new
`include/macws_display_profiles.h` supplies IOMobileFramebuffer SwapEnd
+0x1f84, connection+0x868, swap ID+0xb0 and 0x4fc-byte request;
QuartzCore uses server+0x58/display+0x6328, enabled bit34 at +0x6a34,
and pending vector +0x6558/+0x6560. Callback +0x2c00d8 is PAC signed.
SkyLight EndUpdate(bool,bool) at +0x13e34c retains both arguments and
observes only outermost depth. UUID/instruction guards fail closed.
`misc.test_sonoma_display_submission` compares these profiles with the
actual extracted images and tests wrapper argument forwarding. All63
selected tests and the libmachook cross-build passed.

Both newly built arm64 and arm64e libraries are deployed. Normal production
AGX controls (no utility-only or runtime-diagnostic mode) each returned
`GPU-WITNESS status=4 error=nil` and
`GPU-WITNESS matchingPixels=496/1024 expectedBGRA=106,49,188,255` in
`sonoma-display-gpu-production-arm64{,e}.log`. This is real GPU output,
not a desktop witness. An earlier utility-only test disables Metal setup;
its nil device is not a regression. Optional runtime-diagnostic method
enumeration traps in `class_copyMethodList+0x80`; production avoids that
optional diagnostic, and no PAC/assert bypass was added.

The first full startup passed preferences round-trips, icon/catalog checks,
and LaunchServices seeding, then stopped before WindowServer at authd.
Runtime-confirmed via `authd-correct-target-admission.log`:
`System Policy: launchdchrootexec(83115) deny(1) process-exec* /private/var/mnt/rootfs/System/Library/Frameworks/Security.framework/Versions/A/XPCServices/authd.xpc/Contents/MacOS/authd`
and `failed to apply exec policy`. Its signature still contained only
stock entitlements. Applying the existing merged project signing policy on
a fresh inode admitted the stock executable: `authd-project-sign-control.log`
records `authdb: finished import, succeeded`. With its real launchd service
contract, `authd-launchd-current.log` records PID83160. Direct invocation
without the XPC service contract aborts with `An XPC Service cannot be run directly.`
This is expected and is not the service launch test.

The second full GUI attempt is recorded in
`sonoma-display-second-gui-start.log`. Desktop, runtime display completion,
VNC pixels and compositor correctness are still unverified.


### Storage service fork admission and explicit WindowServer launch

Runtime-confirmed via `diskarbitrationd-native-admission.log`: stock
DiskArbitration was rejected with `unsuitable CT policy 0x8`. The existing
project/native entitlement merge admitted its entry executable, but a PID
alone was misleading: its fork children crashed repeatedly. No current
CrashReporter file was produced (`Corpse failure, too many` was logged).
The bounded crash trace records `xpc_atfork_child+0x88` calling
libdispatch `objc_msgSend$dealloc+0`, then BUS_ADRALN. The added read-only
crash diagnostic records the page's permissions without changing them.
`fork-dispatch-probe-runtime.log` records parent protection5/max7 and
child protection1/max3 on the same0x4000-byte page. Compared executable
words match the actual23A344 libdispatch image. Changing only inheritance
from COPY to SHARE failed too; this is a rejected diagnostic, not a fix.

`fork-dispatch-utility-control.log` records a real child reaching main and
status0 when unnecessary GUI/Metal initialization is omitted. The headless
storage daemon uses the existing static bootstrap interposes, so its launchd
job now sets the established `MACWS_UTILITY_PROCESS=1` contract. Its original
business code and protocol are retained. `diskarbitration-session-witness.log`
records `DA-WITNESS ... description=... keys=30` and `probe-exit=0`, from a
real DASession and DADiskCopyDescription request for disk0. The full GUI start
then completed the real SharedFileList snapshot round-trip. This fixes the
storage daemon's initialization scope; generic GUI-process fork permission
loss remains unresolved and is not claimed fixed.

The subsequent WindowServer timeout initially had no actual WindowServer
PID: the stock job is on demand, while clients are deliberately deferred
until its first frame. `windowserver14-native-launch-control.log` records
OnDemand=true and no PID. The startup script now explicitly starts that
loaded job before waiting for the first frame. This is startup ordering,
not a synthetic readiness marker.

After an explicit start, actual native logs identified two loader mistakes:
`windowserver14-explicit-start-control.log` records `/usr/lib/dyld has entitlements but is not a main binary`.
`dyld14-signature-only.log` confirms the patched loader carried the115-key
project executable profile, while the original14.0 loader had none. Fresh
inode entitlement-free signing preserves all loader instructions. The
WindowServer executable then needed project signing itself: the actual
stock signature already contains the graphics marker formerly used to
assume migration complete. `windowserver14-case-correct-native.log` records
`failed to apply exec policy` for the exact WindowServer target. The generic
signing check now also recognizes stock Apple CMS Authority metadata, with
an executable shell regression test covering stock and migrated cases.

`windowserver14-project-sign-control.log` records real WindowServer PID86137,
followed by `CydiaSubstrate has entitlements but is not a main binary`.
The rootfs framework is a regular independent copy (not a native symlink);
its two slices also carried115 entitlement keys. Both loader dependencies
now use the existing entitlement-free policy in postinst. Their pre-change
images are backed up on the device. The production GUI attempt after these
repairs is `sonoma-display-admission-fixed-gui-start.log`. Its graphics result
is still pending; desktop success remains false.

### WindowServer constructor and actual compositor witnesses

Runtime-confirmed via `windowserver14-constructor-path.log`:
`MACWS INIT entry pid=87821 program=WindowServer utility=<unset> shell=<unset> preferences=<unset>`
and `MACWS INIT image callback registered`. The constructor does not take the
utility/headless early return. `macws_filtered_fprintf` suppresses ordinary
stderr instrumentation in production, so missing routine patch logs are not
evidence that initialization was skipped. The new crash-diagnostic entry
markers use `dprintf` and do not change compatibility behavior.

Runtime-confirmed via `windowserver14-dependencies-ready-native.log`:
`composed=Metal compositor activated. bufferBytes=2` and
`composed=[ Display:Config     ]   display 0x1 bufferBytes=8`.
The actual WindowServer can initialize its compositor with the real service
prerequisites loaded. This is not a framebuffer witness. The first completed
producer marker is still absent. A no-VNC startup control uses the existing
process-readiness path to let actual desktop clients request drawing; it must
not be reported as graphics success without pixel evidence.

### Desktop executable admission and CGSession provider repair

Runtime-confirmed via `sonoma-finder-native-admission.log`: kernel policy
denied the stock Finder executable. Finder, Dock, SystemUIServer and
ControlCenter were backed up before fresh-inode project signing and trust
registration. `sonoma-finder-project-sign-control.log` then reaches Finder's
constructor and captures its FileProvider/CloudDocs initialization crash.

`sonoma-cgsession-appkit-control.log` isolates the failing provider call in a
small AppKit/USR00 program: `CGSSessionCopyCurrentSessionProperties` resolves
to SkyLight, then execution reaches a read-only libapple_nghttp2 data page.
The identical program in `sonoma-cgsession-utility-control.log` calls the
original provider and returns normally. `fileprovider14-searchlist-disasm.txt`
and `fileprovider14-cstrings.txt` confirm FileProvider resolves this exact
provider with dlsym and invokes it at +0xec of `_userDefaultsSearchList`.

Replace the constructor's code-entry rewriting for both CGSession providers
with static dyld interposition. The existing narrow pre-login field handoff
still calls the real provider and preserves unrelated session values.
`test_cgsession_handoff.py` executes these actual wrappers against real
CoreFoundation dictionaries, including nil, non-placeholder and already
logged-in sessions. `sonoma-cgsession-static-runtime.log` confirms the same
AppKit/USR00 program now completes CGSession, CloudDocs and FileProvider calls.
The precise failing trampoline instruction remains uncharacterized; this
repair removes that code-entry rewrite rather than weakening provider checks.

`sonoma-cgsession-static-gpu-control.log` retains real AGX status4 and496/1024
matching pixels, exit0. All68 selected tests pass. The full client startup in
`sonoma-cgsession-fixed-workspace-start.log` now admits all four Aqua agents,
then detects a WindowServer generation change during the VNC pointer proxy
stage and restores iOS. Desktop output is still unverified; the next bounded
diagnostic records the WindowServer crash with actual clients present.

The subsequent `sonoma-workspace-frame-crash-start.log` again admits all four
Aqua agents, Spaces and wallpaper, then times out on Dock's actual input
endpoint. A later standalone WS/Dock diagnostic (`sonoma-workspace-live-diagnostic.log`)
captures Dock aborting in HIServices `_RegisterApplication+0x2fbc`, but the
full startup transaction had already retired its service generation. That
stack does **not** prove the same cause in the full startup and must not be
used to bypass application registration. The bounded jobs were unloaded,
their plist bytes restored, and the iOS interface restored. No desktop pixel
witness has been obtained.

### Sonoma AIR specialization deployment contract

Runtime-confirmed via `sonoma-shader-payload-start.log`: with actual Aqua
clients and service dependencies present, WindowServer aborts in QuartzCore
`create_fragment_shader` while drawing layer backgrounds. Original payload:

```
Metal failed to specialize fragment function
function=fixed_frag_lph_cpf spec=A2Xhfc
error: air version set to 2.6.0 (!10 = !{i32 2, i32 6, i32 0}), but expecting 2.5 in
```

RE-confirmed via `quartzcore14-fragment-shader-abort-disasm.txt` at
QuartzCore UUID DCE2EDB3-C713-39F9-8AF6-3102F2B9B695 + unslid
0x188793100: the abort call carries namespace13/code7, payload x2/x3 and
reason x4. The crash diagnostic only reads bounded memory; abort behavior
remains intact.

`sonoma-specialize-current.log` reproduces the rejection in an independent
real `newFunctionWithName:constantValues:error:` call. Merely admitting all
150 unspecialized functions did not test this compiler operation. The first
17.0 experiment was contaminated by the existing function-set route: its
captured request still contained `air64-apple-ios16.5.0-macabi`.

`sonoma-specialization-ios17-isolated.log` temporarily parks only the
QuartzCore route during the probe, restores it in finally, and succeeds:
`SPECIALIZE-RESULT function=0x1247048c0 domain=nil code=0 error=nil`.
The captured discriminator0xf requests `raw-98215-001-f-116704-f206208670db8a9a.bin`
and `raw-98232-001-f-116704-94fa38e5338842fc.bin` contain respectively the
16.5 and17.0 Catalyst triples. Sonoma's AIR2.6 and shader code remain
unchanged. This supports choosing the actual17.0 deployment contract,
rather than relabelling AIR2.6 as2.5 or disabling compiler validation.

The provisioner now selects `sonoma14-ios17-macabi`, retaining the16.5
profile for reproduction. Existing manifests with the old profile regenerate
all three companions. This repairs the measured specialization contract;
full desktop pixels and further shader/pipeline coverage remain unverified.

### Texture backing surface lookup after specialization repair

Runtime-confirmed via `sonoma-ios17-target-workspace-start.log`: after all
three17.0 companions were installed, the original AIR rejection is absent
and WindowServer reaches SkyLight `SLCADisplay::render_update`. It faults in
`macws_vnc_finish_update+0x4dc`, address0x2620, x8=0x2580. RE-confirmed in the
deployed `libmachook-shader-payload-diag.dylib`: +0x6ced4 loads texture+0x208
and +0x6cee0 dereferences that value+0xa0. The completion observer independently
faults at +0x7c420 on the same layout assumption.

Replace the shared backing lookup and the PF550 completion lookup with the
existing public `MTLTexture.iosurface` getter. No surface is synthesized and
nil remains nil. `test_vnc_surface_contract.py` compiles the actual helper and
checks getter invocation, returned identity, nil and unsupported objects.
Both architectures cross-build and deploy; `sonoma-vnc-surface-gpu-control.log`
retains AGX status4 and496/1024 expected pixels. A bounded full desktop retry
is recorded in `sonoma-vnc-surface-workspace-start.log`.

### Actual final-composite pixels after backing lookup repair

`sonoma-vnc-surface-workspace-start.log` completes actual Aqua startup checks,
including Desktop input and wallpaper RPC, exit0. It does not validate pixels.
Stock `screencapture` exits138 with Bus error. `sonoma-real-stream-capture.log`
uses the existing protocol8 fullscreen subscription and validates the actual
frame descriptor, final-composite flag and lease before importing its Mach
port. Witness: producer6148, `state=ready`, frame flags0x81, IOSurface525,
2388x1668, bytesPerRow9600, BGRA, native capture exit0.

Visual inspection of `sonoma-real-dock-frame.png` shows real Dock icons and
cursor against a black background. This is actual compositor pixel progress,
**not full desktop completion**: wallpaper, menu bar and app windows still
need visual witnesses. Global IOSurface ID lookup failed; only the existing
leased Mach-port transport succeeded. The native capture copies the received
pixels and releases its lease; it does not synthesize a recovery image.

### Terminal signature admission and actual application pixels

Runtime-confirmed via `sonoma-terminal-native-admission.log`: native kernel
activity collection during launch reports the stock Terminal main rejected:

```
AMFI: '/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal': unsuitable CT policy 0x8 for this platform/device, rejecting signature.
AMFI: code signature validation failed.
```

The original is preserved in `sonoma-workspace-originals/Terminal`. Fresh-inode
project signing and registration admit the actual application; root:wheel
ownership is preserved. `postinst.sh` now applies the existing project signing
policy after its regular-file/symlink and ownership checks. The restore test
executes that stanza against both real regular-file and symlink cases.

`sonoma-signed-terminal-capture.log` and `sonoma-terminal-live-control.log`
produce authenticated final-composite captures with a real Terminal window
and Dock. The second control reports `application-active pid=9268
route=NSRunningApplication+HIServices` and one onscreen window ID15, but visual
inspection of `sonoma-terminal-activated-frame.png` still shows no shell prompt,
no menu bar and black background. The initial process snapshot shows Terminal
PID9268 without a child. Activation return values do not establish usability.
The same native collection records stock `/usr/sbin/filecoordinationd` rejected
by AMFI. Its causal relationship to the empty terminal is THEORY, pending a
blocked-call stack or successful real service round-trip. First debugger
attachment failed before a backtrace; no invented stack attribution is used.

The selected regression suite now passes72 tests
(`sonoma-desktop-progress-validation.log`). No full desktop completion claim,
assert bypass, fabricated frame or deletion accompanies this checkpoint.

### Subsequent initialization samples do not establish a display RPC deadlock

`sonoma-terminal-live-stacks-usb.log` captures PID12170's main thread in
SkyLight `get_current_display_system_state+0xf4`, called by `SLSMainDisplayID`,
HIToolbox `_FirstEventTime` and AppKit's event loop. This is one sample, not a
permanent-deadlock witness. Actual14.0 SkyLight symbol and instruction dumps
are `skylight14-symbols.txt` and `skylight14-display-state-request-disasm.txt`.
The request obtains `SLSServerPort`, sends40 bytes and expects64 bytes.

A later generation in `sonoma-display-rpc-terminal-stack.log` instead shows
Terminal during `-[NSApplication init]`, `_initializeSafeAperture`, URL-resource
capability lookup and synchronous LaunchServices registration. It therefore
does not support promoting the earlier display wait into the root cause of
the empty shell. The attempted frame-memory command in that session failed;
no port attribution was obtained. The real WindowServer thread dump was also
captured. Bounded services and debugserver are retired after the observation.
A longer control without debugger stops will sample actual initialization,
process relationships and final-composite frames over80 seconds.

### File coordination admission and dependency control

`sonoma-filecoord-baseline.log` runs the project's real NSFileCoordinator
copy accessor and reports `filecoordinationd crashed`, `accessor=no`, exit1.
The stock main's original SHA256 is
`a4896f79eebb564aa1de36587c740aabc264ff57598c946c6ed24d7d052ce89b`;
its original is preserved before fresh-inode project signing. `postinst.sh`
now includes it in the existing signing policy. The selected suite passes73
checks, including execution of its restoration stanza.

The first independent signed-service test times out and records exit5. This
is an incomplete dependency setup: the prior GUI cleanup had stopped private
DiskArbitration. Runtime-confirmed via `sonoma-filecoordination-diagnostic.log`:
Foundation's `NSFileAccessArbiter initWithQueue:isSubarbiter:listener:+0x324`
calls `CFRelease(NULL)` and traps. RE-confirmed via actual14.0 Foundation
`foundation14-filearbiter-init-disasm.txt` and `foundation14-stubs.txt`:
+0x181e25fc4 calls `DASessionCreate`, retains its result in x25, then
+0x181e260f0/+0x181e260f4 releases that value. This does not justify bypassing
CFRelease or fabricating a DiskArbitration session. A full-service-graph
control is required before claiming file-coordination functionality repaired.

`sonoma-terminal-extended-observation.log` obtains four real final-composite
frames over80 seconds; `sonoma-terminal-observe-0.png` and `...-3.png` both
show the same empty Terminal content. There is no shell child in the sampled
process relationships. This rules out simply declaring the earlier short
pixel capture sufficient; it does not identify the missing initialization.

The full graph control now passes: `sonoma-filecoord-full-graph-control.log`
records `coordinate-copy accessor=yes copied=yes coordination_error=none
copy_error=none`, `FULL_GRAPH_COORDINATION_EXIT 0`. Project signing therefore
repairs the stock daemon's measured admission failure under its required
DiskArbitration service graph. Bare-service failure is retained as a dependency
control, not attributed to another binary incompatibility. The normal repair
script preserves this signing contract. Terminal usability remains unverified.

### Generic fork permission repair and PAM admission (2026-10-02)

Runtime-confirmed via `sonoma-terminal-fork-diagnostic.log`: Terminal's real
forkpty child previously faults in xpc_atfork_child before exec. The child
cache code page is read-only while the corresponding parent page is executable.
`libmachook/Compatibility/MacWSForkFix.c` and `.S` now interpose raw __fork
and use the Dopamine 3.0.10 parent-to-server fork permission repair protocol.
Normal libc atfork callbacks remain intact. Invalid replies and failed repairs
terminate and reap the child rather than continuing with unrepaired mappings.
The upstream MIT notice is retained in the source.

`sonoma-forkfix-deploy-control.log` records `child16844 reached main`,
`status=0`, `fork-exit=0`. Both library slices are deployed. The real GPU
control in `sonoma-forkfix-gpu-control.log` still completes with status4 and
496 nonzero pixels. Full-graph file coordination also continues to pass.

Runtime-confirmed via `sonoma-terminal-forkfix-workspace-control.log`:
Terminal now creates a login child, and native AMFI records
`AMFI: '/usr/lib/pam/pam_nologin.so.2': unsuitable CT policy 0x8 for this platform/device, rejecting signature.`
The seven modules used by the stock login PAM stack are preserved in
`sonoma-workspace-originals` before fresh-inode entitlement-free signing.
`sonoma-pam-signing.log` stores before/after SHA256 and seven trustcache
registrations. postinst replaces their Apple CMS identity without changing
PAM configuration or bypassing account checks. The selected suite now passes
75 tests. A new bounded full-graph Terminal control is underway; a shell
prompt and a complete usable desktop are not yet claimed.

### Real OpenDirectory and account-policy service graph

The first signed PAM control still has an empty real Terminal window.
`sonoma-terminal-pam-other-control.log` no longer records PAM module admission
rejection after the default other stack's pam_deny module is also signed.
`sonoma-pam-direct-control.log` reports actual root identity, nologin success,
and opendirectory service error3. The stock PAM files are unchanged.

RE-confirmed via `pam-opendirectory-account-disasm.txt`: the actual arm64e
pam_sm_acct_mgmt at+0x4410 calls od_record_create_cstring at+0x4548 and retains
its error. That helper calls ODNodeCreateWithNodeType with0x2201 at+0x2984.
Runtime-confirmed via `sonoma-pam-od-service-name.log`: the matching client
requests com.apple.system.opendirectoryd.api and gets a nil authentication
node with OD error10002. This is not inferred to be a password failure.

The first isolated real daemon test crashes after the native collector records
PlistFile.bundle rejected for CT policy0x8. Local.plist specifies that genuine
module for /var/db/dslocal/nodes; Search.plist requires /Local/Default.
PlistFile, search and configure originals are preserved and their library
signatures repaired without application entitlements.

`sonoma-private-od-signed-modules-control.log` then obtains a nonnil real
OD authentication node, but fails PAM with permission denied7. Its daemon
trace explicitly records AccountPolicyHelper lookup failure and a policy
service connection error. This must not be blamed on a disabled root account:
the root record has no authentication_authority field, and the real subsequent
policy evaluation succeeds once its dependency is present.

The initial helper experiment used an irrelevant NSXPCListener factory
adapter. RE of the actual AccountPolicyHelper main at0x100009058 shows
xpc_main at main+0x8c, and the runtime reports `An XPC Service cannot be run
directly.` The factory experiment is removed. The existing libmachook
xpc_main adapter now narrowly accepts the managed root AccountPolicyHelper
job and forwards each real connection to the untouched stock handler.

`sonoma-private-od-policy-adapter-control.log` records OD_AUTH_NODE nonnil,
error0, both direct account modules success0, PAM_ACCOUNT0 success, and
PRIVATE_OD_PAM_EXIT0. Native OD logs record AuthenticationAllowed evaluation
Success and ODRecordAuthenticationAllowed completed.

The tested seven OD Mach names and AccountPolicyHelper XPC client are now
routed to private services in libmachook. Two packaged launchd jobs and
macos_gui.sh publish the graph before Terminal and unload it during GUI cleanup.
Cold-start trust closure includes the two mains, three plugins and eight PAM
modules. postinst preserves their signing policy. Actual adapter/guard and
startup failure tests are added; the selected suite passes78 tests. A bounded
production-script control is running; complete desktop usability remains
unverified until shell output and actual composed pixels are observed.

`sonoma-terminal-production-directory-control.log` verifies the deployed
production graph with PRODUCTION_PAM_EXIT0 and PAM_ACCOUNT0 success.
`sonoma-production-login-control.log` independently enters the real root shell:
login retval0, child sh/bash initialization, and `-sh-3.2#` on a real PTY.
No password policy or PAM check is bypassed.

`sonoma-terminal-input-control.log` samples the real current Terminal PID22359
and its login -pf root child22410, then identifies its actual on-screen window15.
The production Host keyboard protocol sends whoami+Return to that exact PID
and window. The native final-composite captures still show no prompt/output.
This is not a successful UI command round-trip. Earlier filtered ps snapshots
omitted login because they searched /usr/bin/login while ps prints login -pf
root; absence of that match was not evidence of absence of the child.
`sonoma-directory-regression-control.log` retains actual GPU status4,
496/1024 matching pixels, and a fork child that reaches main with wait status0.
The remaining login-child wait is being sampled directly before any new patch.

`sonoma-terminal-login-child-stacks.log` samples login PID23474 in a kernel
syscall with its caller in login. The actual Sonoma login disassembly shows
waitpid at+0x1d60 and the return site at+0x1d64. Main-image load base is not yet
captured, so matching the caller offset remains THEORY until that base or the
full process family is recorded. A login parent waiting for its shell is a
normal possibility, not evidence of another authentication failure. The next
control walks grandchildren and records actual controlling tty values.

`sonoma-terminal-pty-family-control.log` confirms the full actual family:
Terminal24535 → login24558 → foreground -sh24577, sharing ttys000.
Thus the original child-wait theory was wrong: login is waiting for a live
shell. The displayed empty content remains a GUI/output problem to locate,
not proof of an incomplete login chain.

`sonoma-terminal-tty-output-control.log` writes31 bytes to the exact tty of
shell32927 under Terminal32873: MACWS_PTY_OUTPUT_DIAGNOSTIC. Both actual
final-composite observations still show an empty content area. This is a
labelled diagnostic, never a substitute for real shell command output or a
completed UI command round-trip. It narrows the investigation to Terminal's
PTY consumption/text model/drawing and the frame transport, but does not yet
identify which layer is responsible. AppInput-only recording is enabled in
the next bounded experiment without global GPU diagnostics or check bypasses.


`sonoma-terminal-output-live-evidence.log` runtime-confirms hardware records
were routed by macwsinputd through KEYBOARD-PROXY (whoami and Return), rather
than Terminal AppInput. Thus absence of APP-INPUT RX does not establish that
the broker lost the events; successful sendto alone also does not establish
session delivery. The next control samples actual Terminal threads and
compares software keyboard routing. Sonoma Terminal metadata resolves
TTIOManager IOThread=0x10000ea48 and mainThread=0x10001f3a8;
`sonoma-terminal-io-thread-disasm.txt` confirms select at0x10000ebcc,
read at0x10000ec54 and appendBytes:length: at0x10000ecbc.
No output-consumption failure is established until runtime evidence lands.


Runtime-confirmed `sonoma-terminal-output-actual-stacks.log`, PID36231:
main thread HIS_XPC_GetCapsLockLanguageSwitch+0x84 → _SendMessageToHISService
→ synchronous libxpc wait. tty-io thread at Terminal+0xec04 (select return),
main image0x102808000. `sonoma-terminal-software-route-live.log` confirms
AppInput received software whoami character events, but no KEY-EVENT drain.
`sonoma-hiservices-standalone-control.log` copies actual System Policy denial
of HIServicesProxy exec of the stock HIServices main. Main signature inspection
retains Apple CMS and macOS app-sandbox entitlements despite trusted CDHashes.

Minimal repair: fresh-inode project-sign the actual HIServices main, preserve
original at sonoma-workspace-originals/HIServices-main (SHA256 dfb65619e3ae29f6258a5c683128493528118c31c7785c9ed89fdfee3cbf13a7),
register its real CDHash. `sonoma-hiservices-request-control.log` then confirms
the ORIGINAL proxy architecture starts real service PID36695 and actual
HIS_XPC_GetCapsLockLanguageSwitch returns0, request exit0. No check stub,
XPC handler replacement or proxy redesign. postinst now uses the existing
ensure_project_signature_and_trustcache policy instead of trust-only admission.
Full Terminal regression underway; this query alone is not desktop success.

Directory-policy checkpoint: all35 prior archives checked, two new archives
validated (gzip/tar contents and SHA256), manifest37. Includes actual user
homes and dslocal database. HIServices subsequent changes need a new checkpoint.


`sonoma-terminal-hiservices-fixed-control.log` full graph confirms actual
HIServices PID37584 runs and Terminal37522 advances into TIS input layout
interrogation. Authentic frame `sonoma-terminal-hiservices-fixed-frame.png`
remains white content/cursor with Dock. Software keys are received and queued
by AppInput, without KEY-EVENT handling. Thus the HIServices repair is valid
as a service reply repair but does not yet resolve desktop interaction/output.
Another actual main-thread sample is required; no downstream check bypass.


`sonoma-terminal-hiservices-repaired-stacks.log`, PID38584, confirms the
next synchronous wait is now ViewBridge (frame7=0x18fff6e04); HIServices
is no longer in this actual main-thread chain. Runtime System Policy in
`sonoma-viewbridge-start-kernel.log` denies the actual ViewBridgeAuxiliary
stock main exec twice. Original image SHA256 4c5957e67fd077e4170ab0f231af423616f95e4ab5ef48095b848b0ad06ee0e4
is preserved at sonoma-workspace-originals/ViewBridge-main. Fresh-inode
project-signing + trust produces actual PID38896 running through the original
proxy architecture (`sonoma-viewbridge-fixed-live.log`). postinst uses project
signature admission for this second exact executable; no new RPC stub or
response fabrication. Full GUI outcome still to verify after fresh launch.


REAL desktop interaction breakthrough: `sonoma-terminal-service-admission-fixed-frame.png`
shows actual prompt, hardware whoami -> root, menu bar and Dock after the two
upstream service admission repairs. The explicit MACWS_PTY_OUTPUT_DIAGNOSTIC
line is separately labelled and is not counted as command success.

Production (no added application diagnostics) control
`sonoma-production-desktop-soak.log` captures four real final-composite frames.
The initial menu probe correctly refuses an ambiguous shortcut (both New
Window and New Command expose Cmd-N). Exact native menu title selection in
`sonoma-production-real-menu-action.log` is accepted; subsequent runtime
family/window samples confirm new on-screen window29 and independent
login41029 -> foreground sh41035 on ttys001, alongside existing ttys000.
`sonoma-production-soak-final.png` visibly confirms two actual terminal
windows with prompts and the first window's real command result. This is a
completed menu action, not merely an accepted transport request. Black
wallpaper remains, and ViewBridge listener request logs Connection invalid;
these are not declared fixed by process liveness. Extended stability and Host
presentation/pointer interactions remain to validate. 80 relevant tests pass.
Verified backup manifest39 includes original/re-signed HIServices/ViewBridge
images and user data; no user directories deleted this turn.


Runtime-confirmed live production presentation and pointer control:
`sonoma-live-pointer-corrected.log` uses actual native window12 bounds
(X69,Y86,W570,H371), sends a global pointer click at physical158,332,
and observes focused flags77 for window12 vs13 for window29. The actual
`sonoma-live-pointer-corrected.png` shows Terminal foreground/menu and the
real earlier whoami -> root result. Previous fixed-coordinate click hit the
desktop and activated Finder; it was a diagnostic coordinate mistake.

Actual Host final drawable `sonoma-host-pwd-rendered.png` and UIKit screenshot
`sonoma-host-pwd-automation.jpg` visibly present both terminals and Dock.
Host log reports status4/error=nil and fills-screen=YES, while its separate
authority capability/controller-identity fields remain NO. Pixels establish
presentation, not those missing protocol postconditions. `pwd` follow-up
returned sender0 but output is not observed; it is NOT a passed command.
Later authentic capture `sonoma-live-pwd-native.png` includes a real Notes
welcome window; no causal attribution to the keyboard probe is established.

Basic interactive desktop is verified by real command output, completed menu
action, global pointer focus and Host presentation. Full desktop stability,
black wallpaper and the ViewBridge endpoint warning remain open. Production
desktop is left running; no diagnostic debugger or service restart added.

## Sonoma Launchpad folder: IOSurface ownership (2026-10-02)

Runtime-confirmed via `tmp/sonoma-14.0/sonoma-lease-release-evidence.log`:
opening Launchpad/folders grows the plain-texture compatibility pool past its
256 MiB eviction threshold. An IOSurface starts at retain count 1 and reaches
2 after Metal wraps it. SkyLight's `WS::Surface` destructor releases that
surface at count 2. Later, eviction destroys `IOGPUMetalTexture`, whose dealloc
releases the remaining count 1. The pool's explicit CFRelease then traps in
`CF_IS_OBJC`. The trap register value is an internal value, not the pointer
originally supplied by the eviction caller.

RE-confirmed via the actual 23A344 SkyLight binary, UUID
`42FD2E33-2BB2-372F-A01F-B2B36C8277B9`, saved disassembly
`tmp/sonoma-14.0/skylight14-lease-asm.txt`:

- `WS::SurfacePool::Acquire`, plain-texture call return: image +0x5baac.
- Its explicit-IOSurface branch first calls WSIOSurfaceCreateWithFormat, whose
  create ownership is subsequently transferred to the WS::Surface.
- `__shared_ptr_emplace<WS::Surface>::__on_zero_shared` calls `texture.iosurface`
  at +0x5b24c, then CFRelease at +0x5b254, followed by objc_release(texture).
- The plain branch assumes the texture has no IOSurface and provides no
  independent surface retain. Our compatibility allocator violates that
  assumption by returning an IOSurface-backed texture.

The plain-texture hook now transfers one independent IOSurface retain to this
exact constructor call, on both new allocations and pool hits. UUID and return
address checks exclude other callers and the explicit-IOSurface constructor.
The destructor consumes this retain; pool and Metal ownership remain separate.
No release/check is suppressed, and cache eviction remains enabled.

Validation: both dylib slices compiled and deployed; compiled boundary test
`python3 misc/test_skylight_surface_ownership.py` passed. Production startup
used the original WindowServer plist without diagnostic variables or release
observers. The allocation witness reached 262 MiB before eviction, beyond the
old crash trigger. After 12 folder close/open cycles, actual Host-rendered
pixels show the Other folder's icons and backdrop blur. WindowServer PID 54014
and Dock PID 54195 both report `runs = 1` and `last exit code = (never exited)`.
Evidence: `sonoma-launchpad-folder-regression.log` and
`sonoma-launchpad-folder-fixed-after12.png` under `tmp/sonoma-14.0`.
This validates this crash path; it does not certify every macOS application.

## Post-desktop feature audit (2026-10-02)

User confirmed window dragging works, and reported blank Settings, unusable
browser, unresponsive menu bar, unavailable macOS Wi-Fi/Bluetooth controls,
and question-mark application icons. These replace broader assumptions based
on desktop presentation with explicit unresolved feature statuses.

Runtime-confirmed via `SystemSettings.host.log`:
`endpointForReply:withListenerName:replyErrorCode:` reports listener
`com.apple.view-bridge`: `Connection invalid`. A ThemeWidgetControlViewService
whole-service listener request also fails. Settings bridge capability reports
`ready=yes abi=1 capabilities=0x01`; this is not a completed Settings panel.
The lightweight `ExcUserFault_System Settings-2026-10-02-221514.ips` records
`XPC_EXIT_REASON_FAULT`, but its PID 56979 remains observable; the report is
not evidence that the entire process exited.

Runtime-confirmed via `iconservicesagent.log`: Metal library creation reports
`This library format is not supported on this platform (or was built with an
old version of the tools)`. THEORY: this may contribute to question-mark
icons. A correlated per-application icon request/result is still required.

The read-only production menu snapshot request to Terminal PID 58194 times
out with `socket.timeout: timed out`. This establishes a failed round-trip,
not its cause or a failure in every application's menu.

`tmp/sonoma-14.0/sonoma-feature-cli-network.log` records a real chroot echo
and live window catalog. `sonoma-feature-network-full.log` records system
curl requesting https://www.apple.com with SSL_CERT_FILE=/etc/ssl/cert.pem:
`curl: (60) SSL certificate problem: Couldn't understand the server certificate format`.
TLS verification remains enabled; no browser network success is claimed.

`sonoma-feature-audit-20261002.log` captures Host reports for Maps failing
Catalyst scene startup and Messages exiting with an actual UIScreen assertion:
`returning nil screen from mainScreen is not allowed!`. Notes also reports
ViewBridge connection invalid; ActivityMonitor.host.log reports an invalid
AssetCacheManagerService lookup. These apps are not declared fully usable.

No iCloud account operations were attempted. Current upstream READMEs make no
explicit iCloud login/sync promise; iPadOS cloud services are not a macOS
account or synchronization witness. Current feature coverage is in
`ipados17-macos14-update.md`.

## Terminal login service lifecycle fix (2026-10-02)

Runtime-confirmed via `sonoma-login-current-pam.log`: both private directory
jobs are absent, the root record resolves, PAM_START=0, but PAM_ACCOUNT=3
(`error in service module`). Loading the existing AccountPolicy and
OpenDirectory jobs gives PAM_ACCOUNT=0 in
`sonoma-login-services-restored.log`. No account/password state is changed.

Source-confirmed in macos_gui.sh: start_macos_directory_services was inside
WANT_TERMINAL=1, while macwshostd starts the desktop with --no-terminal.
Move the dependency outside that optional application branch. The failure
test executes the actual shell block with both terminal choices and denied
dependency startup, retaining fail-closed return behavior. Four accountpolicy
tests and bash syntax checks pass.

`sonoma-login-restored-pty.log` contains the real stock login -pf root result:
root shell prompt, whoami output root, and macws-login-restored output. Its
test-process teardown encountered a native signal permission error after
successful output; the PTY was closed and the subsequent process inventory
contains no remaining test login. This is not counted as a clean probe exit.

The deployed script preserves GUI processes. A new Terminal launchd process
PID59991 publishes window185, titled root — -sh. The production keyboard
path sends whoami; `sonoma-login-fixed-frame.png` shows real output root and
a shell prompt. `sonoma-login-fixed-capture.log` records an actual IOSurface
2388x1668 capture (CAPTURE_EXIT0). Old interactive-login windows are not
silently reauthenticated. Full reboot/desktop restart regression remains
pending; this validates the missing-dependency cause and new-window login.

## Sonoma CoreImage/compiler and menu follow-up (2026-10-03)

Runtime-confirmed via `coreimage-menu-20261003/coreimage14-current-probe.log`:
stock CoreImage reported `This library format is not supported on this platform
(or was built with an old version of the tools)` and produced no visible pixels.
The captured kind-14 request contained ten modules with the exact target
`air64-apple-macosx14.0.0`. Its reply contained an MTLB at offset 104 whose
target byte was 0x82 and whose triple was `air64-apple-ios17.0.0`.
The captured kind-5 CoreUI request contained two macOS 14 modules; its macOS
output was rejected by the native pipeline with `Target OS is incompatible`.

RE-confirmed via the installed iPadOS 17 images and the read-only
`macws_gpu_compiler_target_probe` (`gpu-compiler-target17.log`): GPUCompiler
UUID `9e166aee7f46396e81b7b3bba347b9cb`, defaultTargetTriple offset 0x2e568,
entry words `d503237f d10303ff a9085ff8 a90957f6`; ComposeFilters UUID
`0a1057e8a6b3316996295943cc696d4a`, compose entry offset 0xa8dc, words
`d503237f d10443ff a90b6ffc a90c67fa`; LLVM UUID
`798e729a2a1c3fcc976ce4b2a86723cb`, GetTarget offset 0xb8a2a8 and SetTarget
0xb8a2c4. Production guards require the supported paired images and entries,
and matching targets across every request-owned module. They use Apple's
Catalyst target constructor and LLVM target setter, retaining compiler and
pipeline validation. The original Ventura compiler profile remains supported.

The old cache migration visited only 31001. The actual Sonoma cache also
contained 32023/libraries.list and libraries.data. The v4 migration archived
24 derived files after stopping the GUI and retiring seven leftover test apps;
a first attempt correctly deferred while those apps were alive. All files
remain in the rootfs retirement journal. Unknown cache versions remain untouched.

Runtime-confirmed via `coreimage14-normal-v4.log`:
`CI-PROBE pixels=256 visible=256 changed-bytes=748 varied-bytes=668 dags=0 hash=f0d3b28ab6d70146`.
Runtime-confirmed via `coreimage14-coreui-v4.log`:
`CI-PROBE pixels=256 visible=256 changed-bytes=226 varied-bytes=672 dags=0 hash=2842d1a2e7ace5d7`.
Both are genuine native GPU renders. The DAG observer reported zero callbacks,
so these results are not claimed as observer-confirmed fresh-DAG executions.
Calendar subsequently displayed both its welcome screen and month view.
Finder's toolbar still showed a magenta square in the final composite;
therefore the compiler fix does not establish that all reported pink UI is fixed.

Runtime-confirmed via Finder.host.log: the metrics publisher queried
resizeIncrements on NSPopoverWindow, whose frame raised
`-[NSPopoverFrame resizeIncrements]: unrecognized selector`. Query that
optional resize metric only for resizable windows. The menu input change
separates Quartz screen inversion from the producer's mapping frame and
invalidates the persistent synthetic position before native CGPost delivery.
Actual screenshots `macws-pointer-selection.png` and `macws-kind-checked.png`
show the Folders grouping and checked Kind item after selection. This validates
one Finder grouping operation, not every submenu or fullscreen route.

Contacts' external LocalSource plugin was present with the actual arm64e ABI0
slice, but dlopen_preflight rejected it before its current CDHash was registered.
The original plugin passed preflight after trustcache registration without
re-signing. The dependency-based admission script now includes the external
Address Book Plug-Ins only for actual AddressBook consumers, confines realpaths
to the rootfs, and preserves original signatures. Contacts' old NSNull crash
ceased; CoreData/ViewBridge errors remain and no complete Contacts UI is claimed.
