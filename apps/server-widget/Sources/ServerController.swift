import AppKit
import CryptoKit
import Darwin
import Foundation

@MainActor
final class ServerController: ObservableObject {
    @Published private var phases: [ServerID: ServerPhase] = [:]
    @Published private var busy: Set<ServerID> = []
    @Published private(set) var projectRoot: URL
    @Published private(set) var errorMessage: String?

    private var refreshing = false
    private var launched: [ServerID: Process] = [:]

    init() {
        let configured = UserDefaults.standard.string(forKey: "FinArchProjectRootOverride")
            ?? (Bundle.main.object(forInfoDictionaryKey: "FinArchProjectRoot") as? String)
            ?? ""
        projectRoot = URL(fileURLWithPath: configured, isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        for service in ServerSpec.all { phases[service.id] = .checking }
    }

    func phase(for service: ServerSpec) -> ServerPhase { phases[service.id] ?? .checking }
    func isBusy(_ service: ServerSpec) -> Bool { busy.contains(service.id) }

    #if PREVIEW
    func previewSetPhase(_ phase: ServerPhase, for service: ServerSpec) {
        phases[service.id] = phase
    }
    #endif

    func refresh() {
        guard !refreshing else { return }
        refreshing = true
        Task {
            for service in ServerSpec.all where !busy.contains(service.id) {
                let observed = await probe(service)
                if !busy.contains(service.id) {
                    if phases[service.id] != observed {
                        event("status", service: service, result: observed.code)
                    }
                    phases[service.id] = observed
                }
            }
            refreshing = false
        }
    }

    func chooseProjectFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "선택"
        panel.directoryURL = projectRoot
        guard panel.runModal() == .OK, let selected = panel.url else { return }
        let root = selected.standardizedFileURL.resolvingSymlinksInPath()
        guard FileManager.default.fileExists(atPath: root.appendingPathComponent("viewer/dataset/start.command").path),
              FileManager.default.fileExists(atPath: root.appendingPathComponent("src/finarch").path) else {
            errorMessage = "fin-arch 프로젝트 폴더를 선택해 주세요."
            return
        }
        projectRoot = root
        UserDefaults.standard.set(root.path, forKey: "FinArchProjectRootOverride")
        errorMessage = nil
        refresh()
    }

    func open(_ service: ServerSpec) { Task { await execute(.open, service) } }
    func start(_ service: ServerSpec) { Task { await execute(.start, service) } }
    func stop(_ service: ServerSpec) { Task { await execute(.stop, service) } }
    func restart(_ service: ServerSpec) { Task { await execute(.restart, service) } }

    enum Action: String { case open, start, stop, restart }

    func execute(_ action: Action, _ service: ServerSpec) async {
        guard !busy.contains(service.id) else { return }
        busy.insert(service.id)
        errorMessage = nil
        defer { busy.remove(service.id) }
        let initial = await probe(service)
        phases[service.id] = initial
        if initial == .occupied {
            fail("\(service.title) 포트 \(service.port)를 다른 서비스나 다른 프로젝트가 사용하고 있어 제어하지 않았습니다.", service, action)
            return
        }
        do {
            switch action {
            case .open:
                if initial == .unresponsive { try await stopAndWait(service) }
                if initial != .running { try await launchAndWait(service) }
                guard NSWorkspace.shared.open(service.address) else {
                    throw ControlError.message("브라우저에서 \(service.title) 화면을 열지 못했습니다.")
                }
            case .start:
                if initial == .unresponsive {
                    throw ControlError.message("\(service.title)이 응답하지 않습니다. 재시작 또는 중지를 사용해 주세요.")
                }
                if initial != .running { try await launchAndWait(service) }
            case .stop:
                if initial == .running || initial == .unresponsive { try await stopAndWait(service) }
            case .restart:
                if initial == .running || initial == .unresponsive { try await stopAndWait(service) }
                try await launchAndWait(service)
            }
            phases[service.id] = await probe(service)
            event(action.rawValue, service: service, result: "OK")
        } catch {
            phases[service.id] = await probe(service)
            fail(error.localizedDescription, service, action)
        }
    }

    private func launchAndWait(_ service: ServerSpec) async throws {
        let script = projectRoot.appendingPathComponent(service.script)
        guard FileManager.default.fileExists(atPath: script.path) else {
            throw ControlError.message("실행 파일이 없습니다: \(service.script)")
        }
        let directory = projectRoot.appendingPathComponent("log/server-widget", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let output = directory.appendingPathComponent("\(service.id.rawValue).log")
        if !FileManager.default.fileExists(atPath: output.path) {
            FileManager.default.createFile(atPath: output.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: output)
        _ = try handle.seekToEnd()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = [script.path, "--no-open", "--port", String(service.port)]
        process.currentDirectoryURL = projectRoot
        process.standardOutput = handle
        process.standardError = handle
        phases[service.id] = .starting
        do {
            try process.run()
        } catch {
            try? handle.close()
            throw error
        }
        try? handle.close()
        launched[service.id] = process
        event("launch", service: service, result: "SPAWNED", pid: process.processIdentifier)
        for _ in 0..<40 {
            let current = await probe(service)
            if current == .running { phases[service.id] = .running; return }
            if !process.isRunning {
                throw ControlError.message("\(service.title) 시작에 실패했습니다. \(output.path) 로그를 확인해 주세요.")
            }
            try await Task.sleep(nanoseconds: 250_000_000)
        }
        throw ControlError.message("\(service.title) 준비 시간을 초과했습니다. \(output.path) 로그를 확인해 주세요.")
    }

    private func stopAndWait(_ service: ServerSpec) async throws {
        let observed = await probe(service)
        if observed == .stopped { return }
        guard observed == .running || observed == .unresponsive else {
            throw ControlError.message("서버 상태가 바뀌어 \(service.title) 중지를 취소했습니다.")
        }
        guard let pid = await listenerPID(service.port),
              let command = await ProcessTools.output("/bin/ps", ["-p", String(pid), "-o", "args="]),
              command.contains(service.processMarker),
              (observed == .running || isKnownExperimentProcess(command, service)) else {
            throw ControlError.message("서버 프로세스를 확인하지 못해 \(service.title)을 중지하지 않았습니다.")
        }
        guard await listenerPID(service.port) == pid else {
            throw ControlError.message("서버 프로세스가 바뀌어 중지를 취소했습니다.")
        }
        phases[service.id] = .stopping
        guard Darwin.kill(pid, SIGTERM) == 0 else {
            throw ControlError.message("\(service.title) 중지 신호를 보내지 못했습니다.")
        }
        event("terminate", service: service, result: "SIGNALLED", pid: pid)
        for _ in 0..<(observed == .unresponsive ? 12 : 40) {
            if await listenerPID(service.port) == nil {
                phases[service.id] = .stopped
                launched.removeValue(forKey: service.id)
                return
            }
            try await Task.sleep(nanoseconds: 250_000_000)
        }
        if observed == .unresponsive {
            guard await listenerPID(service.port) == pid,
                  let currentCommand = await ProcessTools.output("/bin/ps", ["-p", String(pid), "-o", "args="]),
                  isKnownExperimentProcess(currentCommand, service) else {
                throw ControlError.message("서버 프로세스가 바뀌어 \(service.title) 강제 종료를 취소했습니다.")
            }
            guard Darwin.kill(pid, SIGKILL) == 0 else {
                throw ControlError.message("\(service.title) 서버의 강제 종료 신호를 보내지 못했습니다.")
            }
            event("force_terminate", service: service, result: "SIGNALLED", pid: pid)
            for _ in 0..<20 {
                if await listenerPID(service.port) == nil {
                    phases[service.id] = .stopped
                    launched.removeValue(forKey: service.id)
                    return
                }
                try await Task.sleep(nanoseconds: 250_000_000)
            }
        }
        throw ControlError.message("\(service.title) 서버가 제한 시간 안에 중지되지 않았습니다.")
    }

    private func probe(_ service: ServerSpec) async -> ServerPhase {
        var request = URLRequest(url: service.health)
        request.httpMethod = service.id == .experiments ? "HEAD" : "GET"
        request.timeoutInterval = service.id == .experiments ? 3 : 1.5
        request.cachePolicy = .reloadIgnoringLocalCacheData
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else { return .occupied }
            if service.id == .experiments {
                let root = projectRoot.appendingPathComponent("reports/experiments-run").standardizedFileURL.path
                let hash = SHA256.hash(data: Data(root.utf8)).map { String(format: "%02x", $0) }.joined()
                guard http.value(forHTTPHeaderField: "X-Finarch-Viewer") == "experiments",
                      http.value(forHTTPHeaderField: "X-Finarch-Root") == hash else { return .occupied }
                return http.statusCode == 200 ? .running : .unresponsive
            }
            guard http.statusCode == 200 else { return .occupied }
            guard let body = try JSONSerialization.jsonObject(with: data) as? [String: String] else { return .occupied }
            return body["viewer"] == service.id.rawValue && body["project"] == projectRoot.path
                ? .running : .occupied
        } catch {
            guard let pid = await listenerPID(service.port) else { return .stopped }
            if service.id == .experiments,
               let command = await ProcessTools.output("/bin/ps", ["-p", String(pid), "-o", "args="]),
               isKnownExperimentProcess(command, service) {
                return .unresponsive
            }
            return .occupied
        }
    }

    private func isKnownExperimentProcess(_ command: String, _ service: ServerSpec) -> Bool {
        guard service.id == .experiments else { return false }
        let trimmed = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let separator = trimmed.firstIndex(of: " ") else { return false }
        let executable = trimmed[..<separator]
        guard executable == "node" || executable.hasSuffix("/node") else { return false }
        let arguments = trimmed[trimmed.index(after: separator)...]
        let script = projectRoot.appendingPathComponent("src/finarch/experiments/viewer/server.mjs").path
        guard arguments == script || arguments.hasPrefix(script + " ") else { return false }
        let options = arguments.dropFirst(script.count).split(separator: " ")
        return !options.contains("--root")
    }

    private func listenerPID(_ port: Int) async -> pid_t? {
        guard let output = await ProcessTools.output("/usr/sbin/lsof", ["-nP", "-t", "-iTCP:\(port)", "-sTCP:LISTEN"]) else { return nil }
        let values = Set(output.split(whereSeparator: \.isNewline).compactMap { Int32($0) })
        return values.count == 1 ? values.first : nil
    }

    private func fail(_ message: String, _ service: ServerSpec, _ action: Action) {
        errorMessage = message
        event(action.rawValue, service: service, result: "FAIL", detail: message)
    }

    private func event(_ action: String, service: ServerSpec, result: String, pid: pid_t? = nil, detail: String? = nil) {
        let directory = projectRoot.appendingPathComponent("log/server-widget", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let path = directory.appendingPathComponent("events.jsonl")
        var item: [String: Any] = ["time": ISO8601DateFormatter().string(from: Date()),
                                   "action": action, "service": service.id.rawValue,
                                   "port": service.port, "result": result]
        if let pid { item["pid"] = pid }
        if let detail { item["detail"] = detail }
        guard let data = try? JSONSerialization.data(withJSONObject: item),
              var line = String(data: data, encoding: .utf8) else { return }
        line += "\n"
        if !FileManager.default.fileExists(atPath: path.path) {
            FileManager.default.createFile(atPath: path.path, contents: nil)
        }
        guard let handle = try? FileHandle(forWritingTo: path) else { return }
        _ = try? handle.seekToEnd()
        try? handle.write(contentsOf: Data(line.utf8))
        try? handle.close()
    }
}

private enum ControlError: LocalizedError {
    case message(String)
    var errorDescription: String? {
        if case .message(let text) = self { return text }
        return nil
    }
}

private enum ProcessTools {
    static func output(_ executable: String, _ arguments: [String]) async -> String? {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .utility).async {
                let process = Process()
                let pipe = Pipe()
                process.executableURL = URL(fileURLWithPath: executable)
                process.arguments = arguments
                process.standardOutput = pipe
                process.standardError = FileHandle.nullDevice
                do {
                    try process.run()
                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    process.waitUntilExit()
                    continuation.resume(returning: process.terminationStatus == 0
                        ? String(data: data, encoding: .utf8) : nil)
                } catch {
                    continuation.resume(returning: nil)
                }
            }
        }
    }
}
