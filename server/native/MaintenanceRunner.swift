import AppKit
let info = Bundle.main.infoDictionary ?? [:]
guard let python = info["TonePython"] as? String, let script = info["ToneScript"] as? String else { exit(1) }
let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 1 else { exit(1) }
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let process = Process()
let resolved = URL(fileURLWithPath: python).resolvingSymlinksInPath()
let framework = resolved.deletingLastPathComponent().deletingLastPathComponent()
let nativePython = framework.appendingPathComponent("Resources/Python.app/Contents/MacOS/Python")
process.executableURL = FileManager.default.isExecutableFile(atPath: nativePython.path) ? nativePython : resolved
var environment = ProcessInfo.processInfo.environment
environment.removeValue(forKey: "__PYVENV_LAUNCHER__")
environment["PYTHONHOME"] = framework.path
let version = framework.lastPathComponent
let venv = URL(fileURLWithPath: python).deletingLastPathComponent().deletingLastPathComponent()
environment["PYTHONPATH"] = venv.appendingPathComponent("lib/python\(version)/site-packages").path
process.environment = environment
process.arguments = [script] + args
process.currentDirectoryURL = URL(fileURLWithPath: script).deletingLastPathComponent()
process.standardOutput = FileHandle.standardOutput
process.standardError = FileHandle.nullDevice
process.terminationHandler = { child in
    DispatchQueue.main.async { exit(child.terminationStatus) }
}
do { try process.run() } catch { exit(2) }
app.run()
