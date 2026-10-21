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
        print("11 usage model checks passed")
    }
}
