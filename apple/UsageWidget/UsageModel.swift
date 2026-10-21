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
        if minutes == 10080 { return "Ventana de 7 días" }
        if minutes % 60 == 0 { return "Ventana de \(minutes / 60) horas" }
        return "Ventana de \(minutes) minutos"
    }
}

import CoreFoundation
struct UsageSnapshot {
    let primary: UsageWindow?
    let secondary: UsageWindow?
    let plan: String?
    let resetCount: Int?
    let resetCredits: [ResetCredit]
    static func parse(_ value: [String: Any]) -> UsageSnapshot? {
        // This integration currently exposes Codex, not ordinary ChatGPT message quotas.
        let buckets = value["rateLimitsByLimitId"] as? [String: Any]
        let preferred = buckets?["codex"] as? [String: Any]
        let legacy = value["rateLimits"] as? [String: Any]
        guard let bucket = preferred ?? (legacy?["limitId"] as? String == "codex" ? legacy : nil) else { return nil }
        let resets = value["rateLimitResetCredits"] as? [String: Any]
        let countNumber = resets?["availableCount"] as? NSNumber
        let count = countNumber.flatMap { CFGetTypeID($0) != CFBooleanGetTypeID() && $0.doubleValue.isFinite && $0.doubleValue >= 0 && $0.doubleValue == $0.doubleValue.rounded() && $0.doubleValue <= 10000 ? $0.intValue : nil }
        let rows = resets?["credits"] as? [[String: Any]] ?? []
        let credits = rows.compactMap { row -> ResetCredit? in
            guard row["status"] as? String == "available", let id = row["id"] as? String, !id.isEmpty else { return nil }
            let expiry = (row["expiresAt"] as? NSNumber).map { Date(timeIntervalSince1970: $0.doubleValue) }
            guard expiry == nil || expiry! > Date() else { return nil }
            return ResetCredit(id: id, title: (row["title"] as? String).map { String($0.prefix(150)) } ?? "Reinicio de Codex", expires: expiry)
        }
        return UsageSnapshot(primary: UsageWindow.parse(bucket["primary"]), secondary: UsageWindow.parse(bucket["secondary"]), plan: bucket["planType"] as? String, resetCount: count, resetCredits: credits)
    }
}

struct ResetCredit: Equatable {
    let id: String
    let title: String
    let expires: Date?
}
struct ResetOperation: Codable, Equatable {
    let key: String
    let creditId: String?
    var params: [String: Any] {
        var result: [String: Any] = ["idempotencyKey": key]
        if let creditId = creditId { result["creditId"] = creditId }
        return result
    }
    static func create(creditId: String?) -> ResetOperation { ResetOperation(key: UUID().uuidString, creditId: creditId) }
    static func confirmedMessage(_ outcome: String?) -> String? {
        switch outcome {
        case "reset": return "Reinicio aplicado. Consultando los límites nuevos…"
        case "alreadyRedeemed": return "Este reinicio ya estaba aplicado. Actualizando…"
        case "nothingToReset": return "No hay límites que reiniciar. Actualizando disponibilidad…"
        case "noCredit": return "No quedan reinicios disponibles."
        default: return nil
        }
    }
}
