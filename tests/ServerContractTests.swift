import Foundation

@main
struct ServerContractTests {
    static func main() throws {
        let folder = URL(fileURLWithPath: CommandLine.arguments[1])
        let decoder = JSONDecoder()
        let dashboard = try decoder.decode(DashboardResponse.self, from: Data(contentsOf: folder.appendingPathComponent("dashboard.json")))
        _ = try decoder.decode(DealsResponse.self, from: Data(contentsOf: folder.appendingPathComponent("deals.json")))
        _ = try decoder.decode(LogResponse.self, from: Data(contentsOf: folder.appendingPathComponent("logs.json")))
        _ = try decoder.decode(OrbitStatus.self, from: Data(contentsOf: folder.appendingPathComponent("orbit-status.json")))
        precondition(dashboard.statistics.downloadCount >= 0)
        print("Live server contract checks passed (dashboard, deals, logs, Orbit status; no data printed)")
    }
}
