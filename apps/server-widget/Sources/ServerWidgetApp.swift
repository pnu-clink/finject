import AppKit
import SwiftUI

#if !PREVIEW
@main
struct FinArchServerWidgetApp: App {
    @StateObject private var controller = ServerController()

    var body: some Scene {
        MenuBarExtra("FInject Servers", systemImage: "server.rack") {
            ServerPanel(controller: controller)
        }
        .menuBarExtraStyle(.window)
    }
}
#endif

struct ServerPanel: View {
    @ObservedObject var controller: ServerController
    private let timer = Timer.publish(every: 3, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("FInject Servers").font(.headline)
                    Text("Local services · 8893–8896").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    controller.refresh()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Refresh status")
            }

            ForEach(ServerSpec.all) { service in
                serviceRow(service)
                if service.id != ServerSpec.all.last?.id { Divider() }
            }

            if let error = controller.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("server-error")
            }

            Divider()
            HStack {
                Button("Project Folder…") { controller.chooseProjectFolder() }
                Spacer()
                Button("Quit") { NSApp.terminate(nil) }
            }
            .controlSize(.small)
            Text(controller.projectRoot.path)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .truncationMode(.middle)
                .help(controller.projectRoot.path)
        }
        .padding(16)
        .frame(width: 430)
        .onAppear { controller.refresh() }
        .onReceive(timer) { _ in controller.refresh() }
    }

    private func serviceRow(_ service: ServerSpec) -> some View {
        let phase = controller.phase(for: service)
        let busy = controller.isBusy(service)
        return VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 8) {
                Circle()
                    .fill(phase.color)
                    .frame(width: 9, height: 9)
                    .accessibilityLabel(phase.label)
                Text(service.title).fontWeight(.medium)
                Text(verbatim: ":\(service.port)")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                Spacer()
                Text(phase.label).font(.caption).foregroundStyle(.secondary)
            }
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("status-\(service.id.rawValue)")

            HStack(spacing: 6) {
                Button("Open") { controller.open(service) }
                    .help("Start the server if needed, then open it in your browser. Recover a verified unresponsive experiment server first.")
                Button("Start") { controller.start(service) }
                    .disabled(phase != .stopped)
                Button("Stop") { controller.stop(service) }
                    .disabled(phase != .running && phase != .unresponsive)
                Button("Restart") { controller.restart(service) }
                    .disabled(phase == .occupied)
            }
            .controlSize(.small)
            .disabled(busy || phase == .checking || phase == .occupied)
        }
    }
}
