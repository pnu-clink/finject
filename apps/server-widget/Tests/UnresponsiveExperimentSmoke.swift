import AppKit
import Foundation

@main
struct UnresponsiveExperimentSmoke {
    @MainActor
    static func main() async {
        guard CommandLine.arguments.count == 3,
              let expectedPID = Int32(CommandLine.arguments[2]) else {
            fputs("Usage: UnresponsiveExperimentSmoke PROJECT_ROOT EXPECTED_PID\n", stderr)
            exit(2)
        }
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        UserDefaults.standard.set(root.path, forKey: "FinArchProjectRootOverride")
        let service = ServerSpec.all.first { $0.id == .experiments }!
        let untouched = [8893, 8895, 8896].map { ($0, listenerPID($0)) }
        guard listenerPID(service.port) == expectedPID else {
            fputs("FAIL: experiment listener changed before the test\n", stderr)
            exit(1)
        }

        let controller = ServerController()
        controller.refresh()
        for _ in 0..<80 {
            if controller.phase(for: service) != .checking { break }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        guard controller.phase(for: service) == .unresponsive else {
            fputs("FAIL: expected recoverable unresponsive state\n", stderr)
            exit(1)
        }
        print("experiment pid \(expectedPID): unresponsive state PASS")

        let foreignPort = 18994
        guard listenerPID(foreignPort) == nil else {
            fputs("FAIL: unrelated-process test port is occupied\n", stderr)
            exit(1)
        }
        let foreignProcess = Process()
        foreignProcess.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/node")
        foreignProcess.arguments = ["-e", "require('http').createServer((_request,_response)=>{}).listen(18994,'127.0.0.1')"]
        foreignProcess.standardOutput = FileHandle.nullDevice
        foreignProcess.standardError = FileHandle.nullDevice
        do { try foreignProcess.run() }
        catch {
            fputs("FAIL: unrelated-process setup: \(error)\n", stderr)
            exit(1)
        }
        for _ in 0..<30 {
            if listenerPID(foreignPort) == foreignProcess.processIdentifier { break }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        let foreign = ServerSpec(id: .experiments, title: "실험 결과 검사", port: foreignPort,
                                 script: service.script, landing: service.landing,
                                 processMarker: service.processMarker)
        await controller.execute(.restart, foreign)
        let preservedForeign = controller.phase(for: foreign) == .occupied
            && foreignProcess.isRunning && listenerPID(foreignPort) == foreignProcess.processIdentifier
        foreignProcess.terminate()
        foreignProcess.waitUntilExit()
        guard preservedForeign else {
            fputs("FAIL: unrelated unresponsive process was not protected\n", stderr)
            exit(1)
        }
        print("unrelated unresponsive process preserved PASS")

        await controller.execute(.restart, service)
        guard controller.phase(for: service) == .running,
              let newPID = listenerPID(service.port), newPID != expectedPID else {
            fputs("FAIL: experiment restart: \(controller.errorMessage ?? "unknown")\n", stderr)
            exit(1)
        }
        for (port, pid) in untouched where listenerPID(port) != pid {
            fputs("FAIL: service on port \(port) changed\n", stderr)
            exit(1)
        }
        print("experiment pid \(newPID): restart and identity PASS")
        print("other service listeners unchanged PASS")
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
