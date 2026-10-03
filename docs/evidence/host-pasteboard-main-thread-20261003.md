# Host scene delivery blocked by clipboard payload resolution

## Actual waiting caller

Native thread samples of Host PIDs 18118 and 26291 showed the same main-thread
wait. With the installed binary UUID
`CDC87378-B94C-3712-A1EA-2BAB5733602E`, image base `0x1000f4000`,
`atos` resolves the second sample's `0x10014f0d8` frame to:

```text
-[MacWSInteropClient publishGeneralPasteboard]
MacWSInteropClient.m:1036
```

The actual source at that point synchronously reads `pasteboard.items`.
Both Hosts stopped processing new Catalyst launch notifications. A Host-only
restart recovered notification delivery; restarting is not the permanent fix.

## Change

Capture `UIPasteboard.itemProviders` metadata, then use the real asynchronous
`NSItemProvider loadItemForTypeIdentifier:options:completionHandler:` API.
Keep item ordering and representations; failure or timeout publishes no
partial replacement. Completions serialize their results off the main queue.
The main queue checks the clipboard generation before archiving/publishing,
so stale provider results cannot overwrite newer content.

The [Apple NSItemProvider documentation](https://developer.apple.com/documentation/foundation/nsitemprovider)
describes provider loading and completion callbacks. No synchronous payload
read or semaphore wait is used on Host's UI thread.

## Runtime verification and limits

After deployment, the problematic current provider returned an explicit
error instead of blocking the UI:

```text
interop-local-snapshot failed code=-1000
catalyst-host-carrier spawn result=0 child=27768 parent=27742
```

Further Messages and Weather launch requests were processed. A subsequent
native main-thread sample returned to its normal run-loop wait rather than
`publishGeneralPasteboard`. These witnesses verify Host responsiveness.
The producer's `-1000` failure itself remains unresolved, and this does not
claim successful transfer of that producer's content.

The compiled asynchronous test exercises delayed and out-of-order results,
provider failure, timeout followed by a late callback, an empty clipboard,
and a main-queue progress witness while content is pending. It also verifies
that each request completes once. The arm64 Theos Host build succeeded.

Installed Host backup:
`/var/jb/var/mobile/sonoma-workspace-originals/pasteboard-20261003`.
