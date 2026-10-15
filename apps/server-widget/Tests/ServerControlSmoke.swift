import AppKit
import Foundation

@main
struct ServerControlSmoke {
    @MainActor
    static func main() async {
        guard CommandLine.arguments.count == 2 else {
            fputs("Usage: ServerControlSmoke PROJECT_ROOT\n", stderr)
            exit(2)
        }
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        UserDefaults.standard.set(root.path, forKey: "FinArchProjectRootOverride")
        let controller = ServerController()
        var failures: [String] = []

        for service in ServerSpec.all {
            await controller.execute(.start, service)
            if controller.phase(for: service) != .running {
                failures.append("start \(service.id.rawValue): \(controller.errorMessage ?? "unknown error")")
                continue
            }
            let firstPID = listenerPID(service.port)
            await controller.execute(.start, service)
            if controller.phase(for: service) != .running || listenerPID(service.port) != firstPID {
                failures.append("reuse \(service.id.rawValue)")
            }
            await controller.execute(.restart, service)
            if controller.phase(for: service) != .running {
                failures.append("restart \(service.id.rawValue): \(controller.errorMessage ?? "unknown error")")
            }
            await controller.execute(.stop, service)
            if controller.phase(for: service) != .stopped || listenerPID(service.port) != nil {
                failures.append("stop \(service.id.rawValue): \(controller.errorMessage ?? "unknown error")")
            }
            print("service \(service.id.rawValue): start, reuse, restart, stop")
        }

        let research = ServerSpec.all.first { $0.id == .research }!
        let dummy = Process()
        dummy.executableURL = root.appendingPathComponent(".venv/bin/python")
        dummy.arguments = ["-m", "http.server", String(research.port), "--bind", "127.0.0.1"]
        dummy.standardOutput = FileHandle.nullDevice
        dummy.standardError = FileHandle.nullDevice
        do {
            try dummy.run()
            for _ in 0..<20 where listenerPID(research.port) == nil {
                try? await Task.sleep(nanoseconds: 100_000_000)
            }
            await controller.execute(.stop, research)
            if !dummy.isRunning || controller.phase(for: research) != .occupied {
                failures.append("port conflict must leave unrelated process running")
            }
            dummy.terminate()
            dummy.waitUntilExit()
            print("port conflict: unrelated process preserved")
        } catch {
            failures.append("port conflict setup: \(error)")
        }

        await controller.execute(.open, research)
        if controller.phase(for: research) != .running {
            failures.append("open from stopped: \(controller.errorMessage ?? "unknown error")")
        }
        await controller.execute(.stop, research)
        if controller.phase(for: research) != .stopped {
            failures.append("cleanup research: \(controller.errorMessage ?? "unknown error")")
        }
        print("open from stopped: launch and ready")

        if failures.isEmpty {
            print("PASS: all server controls")
        } else {
            for failure in failures { fputs("FAIL: \(failure)\n", stderr) }
            exit(1)
        }
    }

    private static func listenerPID(_ port: Int) -> Int32? {
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        process.arguments = ["-nP", "-t", "-iTCP:\(port)", "-sTCP:LISTEN"]
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        guard (try? process.run()) != nil else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return String(data: data, encoding: .utf8).flatMap { Int32($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
    }
}
