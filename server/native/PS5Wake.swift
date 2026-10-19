import Foundation
// LaunchServices supplies a stable privacy identity. No daemon, network listener or arguments.
let info = Bundle.main.infoDictionary ?? [:]
guard let python = info["TonePython"] as? String,
      let script = info["ToneScript"] as? String else { exit(1) }
let process = Process()
process.executableURL = URL(fileURLWithPath: python)
process.arguments = [script, "--dashboard-helper"] + (CommandLine.arguments.contains("--check-only") ? ["--check-only"] : [])
process.standardOutput = FileHandle.standardOutput
process.standardError = FileHandle.nullDevice
try process.run()
process.waitUntilExit()
exit(process.terminationStatus)
