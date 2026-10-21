import Foundation

@main struct ModelTests {
    static func main() {
        func check(_ condition: Bool, _ message: String) { precondition(condition, message) }
        let window: [String: Any] = ["usedPercent": 33, "windowDurationMins": 300, "resetsAt": 1792628274]
        check(UsageWindow.parse(window)?.remaining == 67, "Convert consumed percentage to remaining")
        check(UsageWindow.parse(["usedPercent": true, "windowDurationMins": 300]) == nil, "Boolean is not usage")
        check(UsageWindow.parse(["usedPercent": 0, "windowDurationMins": 0]) == nil, "Invalid window")
        check(UsageWindow.parse(["usedPercent": 0, "windowDurationMins": 300])?.remaining == 100, "Zero use")
        check(UsageWindow.parse(["usedPercent": 150, "windowDurationMins": 300])?.remaining == 0, "Clamp remaining")
        check(UsageWindow.parse(nil) == nil, "Unknown is not zero or 100")
        check(UsageWindow.parse(["usedPercent": Double.nan, "windowDurationMins": 300]) == nil, "Reject nonfinite values")
        let legacy: [String: Any] = ["limitId": "codex", "primary": window]
        check(UsageSnapshot.parse(["rateLimits": legacy])?.primary?.remaining == 67, "Legacy bucket")
        check(UsageSnapshot.parse(["rateLimitsByLimitId": ["codex": ["primary": ["usedPercent": 40, "windowDurationMins": 300]]], "rateLimits": legacy])?.primary?.remaining == 60, "Prefer explicit multibucket data")
        check(UsageSnapshot.parse(["rateLimits": ["limitId": "other", "primary": window]]) == nil, "Never call a different bucket Codex")
        check(UsageSnapshot.parse(["rateLimits": ["limitId": "codex"]])?.secondary == nil, "Missing weekly quota stays unavailable")
        let available: [String: Any] = ["rateLimits": legacy, "rateLimitResetCredits": ["availableCount": 1, "credits": NSNull()]]
        check(UsageSnapshot.parse(available)?.resetCount == 1, "Count available without credit details")
        check(UsageSnapshot.parse(["rateLimits":legacy])?.resetCount == nil, "Missing reset count is unknown")
        check(UsageSnapshot.parse(["rateLimits":legacy,"rateLimitResetCredits":["availableCount":true]])?.resetCount == nil, "Boolean is not a credit count")
        check(UsageSnapshot.parse(["rateLimits":legacy,"rateLimitResetCredits":["availableCount":-1]])?.resetCount == nil, "Negative reset count is invalid")
        let detailed: [String: Any] = ["rateLimits":legacy,"rateLimitResetCredits":["availableCount":2,"credits":[["id":"expired","status":"available","expiresAt":1],["id":"available","status":"available","title":"Full reset"]]]]
        check(UsageSnapshot.parse(detailed)?.resetCount == 2, "Authoritative count is not number of detail rows")
        check(UsageSnapshot.parse(detailed)?.resetCredits.map(\.id) == ["available"], "Reject expired credits")
        let operation = ResetOperation.create(creditId:"available")
        let restored = try! JSONDecoder().decode(ResetOperation.self, from: JSONEncoder().encode(operation))
        check(restored == operation && restored.params["idempotencyKey"] as? String == operation.key, "Restored request must reuse the same key")
        check(restored.params["creditId"] as? String == "available", "Specific credit selection")
        check(ResetOperation.create(creditId:nil).params["creditId"] == nil, "Allow official server selection when details missing")
        check(ResetOperation.confirmedMessage("alreadyRedeemed") != nil, "Repeated response is resolved")
        check(ResetOperation.confirmedMessage("reset") != nil && ResetOperation.confirmedMessage("noCredit") != nil && ResetOperation.confirmedMessage("nothingToReset") != nil, "Known server outcomes")
        check(ResetOperation.confirmedMessage("unknown") == nil, "Unknown response never claims success")
        print("23 usage and reset model checks passed")
    }
}
