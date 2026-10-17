# FInject Server Widget Source

This folder contains the widget source and Xcode build configuration. The distributed product is `FInjectServerWidget`; the existing Xcode project and scheme retain the name `FinArchServerWidget`. See the [apps guide](../README.md) for the packaged app, installation steps, and screenshots.

| Path | Responsibility |
| --- | --- |
| [Sources/ServerWidgetApp.swift](Sources/ServerWidgetApp.swift) | Menu-bar icon and server-control panel. |
| [Sources/ServerController.swift](Sources/ServerController.swift) | Repository selection, server identification, start/stop/restart, and browser opening. |
| [Sources/ServerSpec.swift](Sources/ServerSpec.swift) | Service order, names, ports, launch scripts, and URLs. |
| [FinArchServerWidget.xcodeproj](FinArchServerWidget.xcodeproj) | Xcode project. |
| [project.yml](project.yml) | XcodeGen definition. XcodeGen is not needed to build the supplied Xcode project. |
| [Config/Info.plist](Config/Info.plist) | App metadata and English localization declaration. |
| [Tests/](Tests/) | Existing widget checks. |

## Build from source

On a Mac with Xcode installed, run the following from the repository root. Build output goes to a temporary directory, keeping this folder limited to source and build configuration.

```sh
xcodebuild \
  -project apps/server-widget/FinArchServerWidget.xcodeproj \
  -scheme FinArchServerWidget \
  -configuration Release \
  -derivedDataPath /tmp/finject-widget-build \
  ARCHS='arm64 x86_64' ONLY_ACTIVE_ARCH=NO CODE_SIGNING_ALLOWED=NO build
open /tmp/finject-widget-build/Build/Products/Release/FInjectServerWidget.app
```

Choose the repository root using **Project Folder…**. The app ZIP does not embed Python, Node.js, or the viewer server code. Follow the [environment setup](../README.md#1-prepare-the-viewer-environment-once) before starting a server.

Generated from `src/finarch/documentation/templates/server-widget.md`.
