# Mail system-symbol requests require the main thread

## Failure and actual binary evidence

Runtime-confirmed via Mail-2026-10-04-000055.ips, PID 30866:

- The last exception includes MailUI+0x6b910,
  +[NSImage(SystemSymbolAdditions)
  mf_imageWithSystemSymbolName:hintScale:hintFont:accessibilityDescription:].
- Its caller is Mail+0x18ecc8, reached from a block through
  EFQueueScheduler and a libdispatch worker queue.
- The main thread is separately constructing views from a nib.

RE-confirmed via the actual Sonoma MailUI image, UUID
C3CF263D-5CD6-3746-8468-625078A9FAE3:

- The method starts at 0x1bccd6730.
- Its call at +0x58 (0x1bccd6788) uses the stub at 0x1bcd6d030.
  Reading that stub's actual shared-cache slot at 0x1da878410 resolves
  to 0x1804329c4: the pthread_main_np implementation.
- +0x5c compares the result with 1. The failing branch goes to
  0x1bccd68d8 and invokes the original assertion handler.
- The assertion's actual constant string is Current thread must be main.
- Actual image generation occurs later in the cache-generator block, which
  calls imageWithPrivateSystemSymbolName:accessibilityDescription:.

The runtime method encoding is @48@0:8@16q24@32@40. Thus this was a
thread-affinity violation, not evidence that a symbol asset was missing.

## Change and boundaries

MacWSMailSymbolThread installs only in the Mail process and only on the
MailUI category method with the confirmed encoding and image origin.
Calls on the main thread retain their original direct path. Background
requests synchronously execute the same original method on the main queue.

The actual NSImage result is retained across the main queue's autorelease
pool and autoreleased into the requesting thread's pool. Original nil
results and exceptions propagate unchanged. No check, assertion, or image
creation is bypassed.

The compiled test exercises real main-queue dispatch using a main run loop,
including result lifetime, nil results, and original exception propagation.
Both library architectures build successfully.

## Device validation and remaining work

The deployed library opened Mail as PID 32325. A genuine WindowServer
capture showed the initial Mail Privacy Protection interface and its
real system symbols. An exact-window input record selected Protect Mail
Activity: the real radio button and card became selected and Continue became
enabled. The user explicitly chose this setting.

The next exact-window input activated Continue. A subsequent real capture
showed that the privacy window had closed and the main Mail window displayed
its mailbox sidebar and download status. The same Mail process remained
responsive through this interaction. This also exercises the main-queue
routing with a live AppKit run loop; it is not just a process-lifetime check.

This verifies rendering and input beyond process uptime. It does not establish
successful account synchronization or all Mail features. A separate log still
reports Cocoa error 134020 about incompatible store configuration; this is
tracked independently without deleting any user database.

Previous libraries are retained under
/var/jb/var/mobile/sonoma-workspace-originals/mail-symbol-20261004.
The private device captures are not committed.
