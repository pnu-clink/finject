import AppKit
import SwiftUI

#if !PREVIEW
@main
struct FinArchServerWidgetApp: App {
    @StateObject private var controller = ServerController()

    var body: some Scene {
        MenuBarExtra("FinArch Servers", systemImage: "server.rack") {
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
                    Text("fin-arch 서버").font(.headline)
                    Text("로컬 서비스 · 8893–8896").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    controller.refresh()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("상태 새로고침")
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
                Button("프로젝트 폴더…") { controller.chooseProjectFolder() }
                Spacer()
                Button("종료") { NSApp.terminate(nil) }
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
                Button("열기") { controller.open(service) }
                    .help("꺼져 있으면 시작하고, 확인된 실험 서버가 응답하지 않으면 재시작한 뒤 엽니다")
                Button("시작") { controller.start(service) }
                    .disabled(phase != .stopped)
                Button("중지") { controller.stop(service) }
                    .disabled(phase != .running && phase != .unresponsive)
                Button("재시작") { controller.restart(service) }
                    .disabled(phase == .occupied)
            }
            .controlSize(.small)
            .disabled(busy || phase == .checking || phase == .occupied)
        }
    }
}
