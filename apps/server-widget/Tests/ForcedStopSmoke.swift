import AppKit
import Darwin
import Foundation

@main
struct ForcedStopSmoke {
    @MainActor
    static func main() async {
        guard CommandLine.arguments.count == 2 else { exit(2) }
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        UserDefaults.standard.set(root.path, forKey: "FinArchProjectRootOverride")
        let port = 18995
        guard listenerPID(port) == nil else {
            fputs("FAIL: test port occupied\n", stderr)
            exit(1)
        }
        let experiment = ServerSpec.all.first { $0.id == .experiments }!
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/node")
        process.arguments = [root.appendingPathComponent("src/finarch/experiments/viewer/server.mjs").path,
                             "--no-open", "--port", String(port)]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do { try process.run() }
        catch {
            fputs("FAIL: test server launch: \(error)\n", stderr)
            exit(1)
        }
        let pid = process.processIdentifier
        defer {
            if process.isRunning { _ = Darwin.kill(pid, SIGKILL) }
            process.waitUntilExit()
        }
        for _ in 0..<30 {
            if listenerPID(port) == pid { break }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        guard listenerPID(port) == pid, Darwin.kill(pid, SIGSTOP) == 0 else {
            fputs("FAIL: test server did not reach stopped simulation\n", stderr)
            exit(1)
        }
        let target = ServerSpec(id: .experiments, title: "Experiment recovery check", port: port,
                                script: experiment.script, landing: experiment.landing,
                                processMarker: experiment.processMarker)
        let controller = ServerController()
        await controller.execute(.stop, target)
        guard controller.phase(for: target) == .stopped, listenerPID(port) == nil else {
            fputs("FAIL: verified forced stop: \(controller.errorMessage ?? "unknown")\n", stderr)
            exit(1)
        }
        print("verified unresponsive experiment: SIGTERM timeout, same PID recheck, SIGKILL PASS")
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
        return String(data: data, encoding: .utf8)
            .flatMap { Int32($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
    }
}
