import AppKit
import ApplicationServices

// Read only the code displayed by Orbit, never cookies or the credential store.
func finish(_ value: [String: String], status: Int32 = 0) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: value)
    FileHandle.standardOutput.write(data)
    exit(status)
}
func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var result: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &result) == .success else { return nil }
    return result
}
func text(_ element: AXUIElement) -> String {
    for name in [kAXTitleAttribute, kAXValueAttribute, kAXDescriptionAttribute] {
        if let value = attribute(element, name) as? String, !value.isEmpty { return value }
    }
    return ""
}
func nodes(_ root: AXUIElement) -> [AXUIElement] {
    var result: [AXUIElement] = []
    func visit(_ node: AXUIElement, _ depth: Int) {
        guard depth < 40, result.count < 10000 else { return }
        result.append(node)
        for child in attribute(node, kAXChildrenAttribute) as? [AXUIElement] ?? [] { visit(child, depth + 1) }
    }
    visit(root, 0)
    return result
}
func readCode(_ elements: [AXUIElement]) -> String? {
    let labels = ["Pairing code", "Código de vinculación", "Código de emparejamiento"]
    for (index, element) in elements.enumerated() {
        let value = text(element).trimmingCharacters(in: .whitespacesAndNewlines)
        guard labels.contains(value) else { continue }
        for candidate in elements.dropFirst(index + 1).prefix(4) {
            let code = text(candidate).trimmingCharacters(in: .whitespacesAndNewlines)
            if code.range(of: "^[0-9]{6}$", options: .regularExpression) != nil { return code }
        }
    }
    return nil
}
let prompt = CommandLine.arguments.contains("--request-permission")
let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: prompt] as CFDictionary
if !AXIsProcessTrustedWithOptions(options) { finish(["error": "permission"], status: 1) }
guard let app = NSWorkspace.shared.runningApplications.first(where: {
    $0.bundleURL?.standardizedFileURL.path == "/Applications/Orbit Zero.app"
}) else { finish(["error": "not_running"], status: 1) }
let root = AXUIElementCreateApplication(app.processIdentifier)
AXUIElementSetMessagingTimeout(root, 2)
// Electron may not expose its HTML accessibility tree until a client opts in.
AXUIElementSetAttributeValue(root, "AXManualAccessibility" as CFString, kCFBooleanTrue)
AXUIElementSetAttributeValue(root, "AXEnhancedUserInterface" as CFString, kCFBooleanTrue)
var elements = nodes(root)
for _ in 0..<10 {
    if elements.contains(where: { ["Consola", "Console"].contains(text($0)) }) { break }
    Thread.sleep(forTimeInterval: 0.2)
    elements = nodes(root)
}
if let code = readCode(elements) { finish(["code": code]) }
if let console = elements.first(where: {
    (attribute($0, kAXRoleAttribute) as? String) == kAXButtonRole && ["Consola", "Console"].contains(text($0))
}) {
    AXUIElementPerformAction(console, kAXPressAction as CFString)
    for _ in 0..<10 {
        Thread.sleep(forTimeInterval: 0.2)
        elements = nodes(root)
        if elements.contains(where: { ["Cómo funciona", "How it works"].contains(text($0)) }) { break }
    }
}
if let code = readCode(elements) { finish(["code": code]) }
if let help = elements.first(where: {
    (attribute($0, kAXRoleAttribute) as? String) == kAXButtonRole && ["Cómo funciona", "How it works"].contains(text($0))
}) {
    AXUIElementPerformAction(help, kAXPressAction as CFString)
    Thread.sleep(forTimeInterval: 0.25)
}
if let code = readCode(nodes(root)) { finish(["code": code]) }
finish(["error": "not_visible"], status: 1)
