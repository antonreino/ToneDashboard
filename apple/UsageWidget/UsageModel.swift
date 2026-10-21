import Foundation

struct UsageWindow: Equatable {
    let remaining: Double
    let minutes: Int
    let reset: Date?
    static func parse(_ raw: Any?) -> UsageWindow? {
        guard let value = raw as? [String: Any],
              let used = value["usedPercent"] as? NSNumber,
              CFGetTypeID(used) != CFBooleanGetTypeID(), used.doubleValue.isFinite,
              let duration = value["windowDurationMins"] as? Int, duration > 0 else { return nil }
        let reset = (value["resetsAt"] as? NSNumber).flatMap { $0.doubleValue > 0 ? Date(timeIntervalSince1970: $0.doubleValue) : nil }
        return UsageWindow(remaining: max(0, min(100, 100-used.doubleValue)), minutes: duration, reset: reset)
    }
    var title: String {
        if minutes == 10080 { return "Semanal" }
        if minutes % 60 == 0 { return "Ventana de \(minutes / 60) horas" }
        return "Ventana de \(minutes) minutos"
    }
}

import CoreFoundation
struct UsageSnapshot {
    let primary: UsageWindow?
    let secondary: UsageWindow?
    let plan: String?
    static func parse(_ value: [String: Any]) -> UsageSnapshot? {
        // This integration currently exposes Codex, not ordinary ChatGPT message quotas.
        let buckets = value["rateLimitsByLimitId"] as? [String: Any]
        let preferred = buckets?["codex"] as? [String: Any]
        let legacy = value["rateLimits"] as? [String: Any]
        guard let bucket = preferred ?? (legacy?["limitId"] as? String == "codex" ? legacy : nil) else { return nil }
        return UsageSnapshot(primary: UsageWindow.parse(bucket["primary"]), secondary: UsageWindow.parse(bucket["secondary"]), plan: bucket["planType"] as? String)
    }
}
