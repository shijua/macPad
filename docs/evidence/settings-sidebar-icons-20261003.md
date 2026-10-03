# Sonoma Settings sidebar icons

## Actual failure boundary

Runtime-confirmed in `SystemSettings.host.log`, fresh Settings PID 20780:

```text
MACWS SETTINGS concrete icon class=ISBundleIdentifierIcon descriptor=ISImageDescriptor provider=ISRecordResourceProvider graphic=0 resource=nil replacement=nil size=24.0x24.0 scale=2.0
```

An independent request for General's actual LaunchServices extension record
returned the correct URL and `ISGraphicIconConfiguration` dictionary. Its
provider reports `supportsGraphicIcons=0`. After normal `resolveResources`:

```text
RESOLVED_RESOURCE IDENTIFIER resource=ISGraphicSymbolResource symbol=nil
GRAPHIC IDENTIFIER supported=0
DIRECT_ICON IDENTIFIER image=1 visible=0 colored=0
DIRECT_ICON SYMBOL image=1 visible=1750 colored=1347
```

The last line renders the actual graphic resource's recipe at 24 points,
scale 2. A non-nil CGImage alone is insufficient: the identifier route is
fully transparent. The old compatibility hook incorrectly used the
provider's capability flag to decide whether to resolve its resource.

Siri uses a different real resource:

```text
RESOLVED_RESOURCE IDENTIFIER resource=ISAssetCatalogResource symbol=nil
ACTUAL_ASSET_RESOURCE image=1 visible=1646 colored=1506
DIRECT_ICON IDENTIFIER image=1 visible=0 colored=0
```

Its bundle declares `CFBundleIconFile=AppIconSiri`; it does not declare a
graphic symbol configuration. It must retain that asset artwork.

## Binary cross-check

RE-confirmed via extracted 23A344 `IconServices`:

- `-[ISBundleIdentifierIcon makeSymbolResourceProvider]` at `0x18e5519dc`
  selects `_makeResourceProviderAllowIconResourceFallback:` with argument 0.
- `-[ISRecordResourceProvider resolveResources]` at `0x18e574bd0` obtains
  the record's icon dictionary and calls the normal resource factory at
  `0x18e574cd8`.
- `-[ISConcreteIcon _imageForSymbolImageDescriptor:]` at `0x18e55bf0c`
  requests `symbol` from the provider at `0x18e55bf44` and renders that
  object at `0x18e55bf58`. The runtime provider's symbol is nil even though
  its real icon resource exists.

The extraction tool's unrelated indirect-symbol stub labels are unreliable;
the observations above use the actual ObjC selector call sites and runtime
method signatures.

## Fix and verification

Resolve the provider normally, then select the real graphic resource by
class. Do not force `supportsGraphicIcons` to YES. Asset-catalog resources
are accepted only from an actual `LSApplicationExtensionRecord` whose file
URL is a Settings `.appex` below the two known extension directories. Other
resources and errors keep the original IconServices path.

Both arm64 and arm64e libraries built and deployed. All 50 Settings extension
dependency copies were reconciled. The actual Settings window (PID 25080)
shows the restored colored sidebar icons, including Siri & Spotlight.
Local capture: `tmp/sonoma-14.0/priority-20261003/settings-sidebar-icons-fixed.png`.
The screenshot remains local because unrelated applications are visible.

Tests compile the actual resolver and exercise a false capability flag with
a real graphic resource, absent/wrong resources, valid asset records, wrong
record types, remote URLs and directory traversal. Related regression batch:
21 tests passed. Device originals are retained in
`/var/jb/var/mobile/sonoma-workspace-originals/settings-icon-20261003/`.

A diagnostic Settings launch with the global runtime-diagnostics switch
crashed in `class_copyMethodList` from the AGX memoryless witness. The normal
production launch does not enable that diagnostic. This separate diagnostic
failure is not attributed to sidebar icons.
