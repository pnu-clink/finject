import AppKit
import Foundation
import SwiftUI

@main
struct RenderPreview {
    @MainActor
    static func main() async {
        guard CommandLine.arguments.count == 3 || CommandLine.arguments.count == 4 else { exit(2) }
        UserDefaults.standard.set(CommandLine.arguments[1], forKey: "FinArchProjectRootOverride")
        let controller = ServerController()
        controller.refresh()
        for _ in 0..<40 {
            if ServerSpec.all.allSatisfy({ controller.phase(for: $0) != .checking }) { break }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        if CommandLine.arguments.count == 4,
           CommandLine.arguments[3] == "experiment-unresponsive",
           let experiment = ServerSpec.all.first(where: { $0.id == .experiments }) {
            controller.previewSetPhase(.unresponsive, for: experiment)
        }
        let view = ServerPanel(controller: controller)
            .environment(\.colorScheme, .light)
            .background(Color.white)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        guard let image = renderer.nsImage,
              let tiff = image.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiff),
              let png = bitmap.representation(using: .png, properties: [:]) else { exit(1) }
        do {
            try png.write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
        } catch { exit(1) }
    }
}
