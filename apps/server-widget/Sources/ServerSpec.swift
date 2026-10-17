import Foundation
import SwiftUI

enum ServerID: String, CaseIterable, Identifiable {
    case dataset
    case experiments
    case dashboard
    case research

    var id: String { rawValue }
}

struct ServerSpec: Identifiable {
    let id: ServerID
    let title: String
    let port: Int
    let script: String
    let landing: String
    let processMarker: String

    static let all: [ServerSpec] = [
        .init(id: .dataset, title: "Dataset", port: 8893,
              script: "viewer/dataset/start.command", landing: "/",
              processMarker: "finarch.dataset.viewer.server"),
        .init(id: .experiments, title: "Experiments", port: 8894,
              script: "viewer/experiments/start.command", landing: "/",
              processMarker: "finarch/experiments/viewer/server.mjs"),
        .init(id: .dashboard, title: "Dashboard", port: 8895,
              script: "viewer/dashboard/start.command", landing: "/dashboard/03-project/",
              processMarker: "finarch.dashboard.viewer.server"),
        .init(id: .research, title: "Research", port: 8896,
              script: "viewer/research/start.command", landing: "/viewer/research/",
              processMarker: "finarch.shared.research_viewer"),
    ]

    var address: URL { URL(string: "http://127.0.0.1:\(port)\(landing)")! }
    var health: URL {
        URL(string: "http://127.0.0.1:\(port)\(id == .experiments ? "/" : "/api/health")")!
    }
}

enum ServerPhase: Equatable {
    case checking
    case stopped
    case running
    case unresponsive
    case occupied
    case starting
    case stopping

    var code: String {
        switch self {
        case .checking: return "CHECKING"
        case .stopped: return "STOPPED"
        case .running: return "RUNNING"
        case .unresponsive: return "UNRESPONSIVE"
        case .occupied: return "OCCUPIED"
        case .starting: return "STARTING"
        case .stopping: return "STOPPING"
        }
    }

    var label: String {
        switch self {
        case .checking: return "Checking"
        case .stopped: return "Stopped"
        case .running: return "Running"
        case .unresponsive: return "Not responding"
        case .occupied: return "Port in use / unverified"
        case .starting: return "Starting"
        case .stopping: return "Stopping"
        }
    }

    var color: Color {
        switch self {
        case .running: return .green
        case .stopped: return .red
        case .unresponsive, .occupied: return .orange
        case .checking, .starting, .stopping: return .gray
        }
    }
}
