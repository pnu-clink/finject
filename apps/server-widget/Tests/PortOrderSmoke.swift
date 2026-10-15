import AppKit
import Foundation

@main
struct PortOrderSmoke {
    @MainActor
    static func main() async {
        guard CommandLine.arguments.count == 2 else {
            fputs("Usage: PortOrderSmoke PROJECT_ROOT\n", stderr)
            exit(2)
        }
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        UserDefaults.standard.set(root.path, forKey: "FinArchProjectRootOverride")

        let expected: [(ServerID, Int)] = [
            (.dataset, 8893), (.experiments, 8894), (.dashboard, 8895), (.research, 8896)
        ]
        guard ServerSpec.all.map({ ($0.id, $0.port) }).elementsEqual(expected, by: {
            $0.0 == $1.0 && $0.1 == $1.1
        }) else {
            fputs("FAIL: widget order or port assignment\n", stderr)
            exit(1)
        }

        let controller = ServerController()
        let preserved = Dictionary(uniqueKeysWithValues: ServerSpec.all.suffix(2).map {
            ($0.id, listenerPID($0.port))
        })
        for service in ServerSpec.all {
            await controller.execute(.start, service)
            guard controller.phase(for: service) == .running,
                  let pid = listenerPID(service.port) else {
                fputs("FAIL: \(service.id.rawValue) at \(service.port): \(controller.errorMessage ?? "unknown")\n", stderr)
                exit(1)
            }
            await controller.execute(.start, service)
            guard controller.phase(for: service) == .running,
                  listenerPID(service.port) == pid else {
                fputs("FAIL: \(service.id.rawValue) reuse\n", stderr)
                exit(1)
            }
            if let oldPID = preserved[service.id] ?? nil, oldPID != pid {
                fputs("FAIL: \(service.id.rawValue) was replaced\n", stderr)
                exit(1)
            }
            print("\(service.id.rawValue): port \(service.port), running pid \(pid), reuse PASS")
        }
        print("PASS: ordered ports and four running services")
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
