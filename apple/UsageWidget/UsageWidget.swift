import AppKit
import SwiftUI
import Combine

final class UsageStore: ObservableObject {
    @Published var snapshot: UsageSnapshot?
    @Published var lastRead: Date?
    @Published var message = "Consultando límites…"
    @Published var connected = false
    func received(_ snapshot: UsageSnapshot) {
        self.snapshot = snapshot; self.lastRead = Date(); self.connected = true
        self.message = "Consulta cada 3 segundos"
    }
    func failed(_ message: String) { self.connected = false; self.message = message }
}

// One stdio child while the widget is open. No HTTP listener, prompts or agent turns.
final class UsageClient {
    private let queue = DispatchQueue(label: "ovh.tone.usage.rpc", qos: .utility)
    private var process: Process?
    private var input: FileHandle?
    private var output: FileHandle?
    private var buffer = Data()
    private var timer: DispatchSourceTimer?
    private var initialized = false
    private var pending: (Int, Date)?
    private var sequence = 1
    private var nextAttempt = Date.distantPast
    private var failures = 0
    private var stopping = false
    private let store: UsageStore
    private let executable = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
    init(store: UsageStore) { self.store = store }
    func start() {
        queue.async { [self] in
            let timer = DispatchSource.makeTimerSource(queue: self.queue)
            timer.schedule(deadline: .now(), repeating: 3, leeway: .milliseconds(200))
            timer.setEventHandler { [weak self] in self?.tick() }
            self.timer = timer; timer.resume()
        }
    }
    func stop() { queue.sync { stopping = true; timer?.cancel(); timer = nil; disconnect() } }
    func refresh() { queue.async { self.nextAttempt = .distantPast; self.tick() } }
    private func tick() {
        guard !stopping else { return }
        if let request = pending {
            if Date().timeIntervalSince(request.1) > 15 { fail("La consulta no responde; reintentando…") }
            return
        }
        guard Date() >= nextAttempt else { return }
        if process == nil { connect() }
        else if initialized { requestLimits() }
    }
    private func connect() {
        guard FileManager.default.isExecutableFile(atPath: executable) else { fail("No se encuentra Codex en este Mac."); return }
        let child = Process(); let stdin = Pipe(); let stdout = Pipe()
        child.executableURL = URL(fileURLWithPath: executable)
        child.arguments = ["app-server", "--listen", "stdio://"]
        child.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
        child.standardInput = stdin; child.standardOutput = stdout; child.standardError = FileHandle.nullDevice
        stdout.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let bytes = handle.availableData
            self?.queue.async { [weak self] in self?.read(bytes) }
        }
        child.terminationHandler = { [weak self, weak child] _ in
            self?.queue.async { [weak self, weak child] in
                guard let self = self, self.process === child, !self.stopping else { return }
                self.fail("Conexión cerrada; reintentando…")
            }
        }
        do {
            try child.run(); process = child; input = stdin.fileHandleForWriting; output = stdout.fileHandleForReading
            pending = (0, Date())
            send(["id": 0, "method": "initialize", "params": ["clientInfo": ["name": "tone_usage_widget", "title": "Tone Usage Widget", "version": "1.0.0"]]])
        } catch { stdout.fileHandleForReading.readabilityHandler = nil; fail("No se pudo abrir la consulta de Codex.") }
    }
    private func send(_ message: [String: Any]) {
        guard var data = try? JSONSerialization.data(withJSONObject: message) else { return }
        data.append(10)
        do { try input?.write(contentsOf: data) } catch { fail("No se pudo consultar Codex.") }
    }
    private func requestLimits() {
        sequence += 1; pending = (sequence, Date())
        send(["id": sequence, "method": "account/rateLimits/read", "params": [:]])
    }
    private func read(_ bytes: Data) {
        guard !bytes.isEmpty else { return }
        buffer.append(bytes)
        guard buffer.count <= 524288 else { fail("Respuesta no válida; reintentando…"); return }
        while let end = buffer.firstIndex(of: 10) {
            let line = buffer.prefix(upTo: end); buffer.removeSubrange(...end)
            guard let value = (try? JSONSerialization.jsonObject(with: line)) as? [String: Any] else { continue }
            if let id = value["id"] as? Int, id == pending?.0 {
                pending = nil
                if value["error"] != nil {
                    fail("No se pudieron leer los límites. Revisa la sesión de Codex."); return
                }
                if id == 0 {
                    initialized = true; send(["method": "initialized", "params": [:]]); requestLimits()
                } else if let result = value["result"] as? [String: Any] { publish(result) }
            } else if value["method"] as? String == "account/rateLimits/updated", let params = value["params"] as? [String: Any] { publish(params) }
        }
    }
    private func publish(_ value: [String: Any]) {
        guard let snapshot = UsageSnapshot.parse(value) else { fail("La cuenta no devuelve límites de Codex disponibles."); return }
        failures = 0
        DispatchQueue.main.async { self.store.received(snapshot) }
    }
    private func fail(_ message: String) {
        disconnect(); failures += 1
        let delay = min(60.0, 3.0 * pow(2.0, Double(min(failures-1, 5))))
        nextAttempt = Date().addingTimeInterval(delay)
        DispatchQueue.main.async { self.store.failed(message) }
    }
    private func disconnect() {
        output?.readabilityHandler = nil
        let child = process; process = nil
        try? input?.close(); try? output?.close(); input = nil; output = nil
        if child?.isRunning == true { child?.terminate() }
        initialized = false; pending = nil; buffer.removeAll(keepingCapacity: true)
    }
}

struct UsageView: View {
    @ObservedObject var store: UsageStore
    let refresh: () -> Void
    let quit: () -> Void
    private let ink = Color(red: 0.17, green: 0.24, blue: 0.20)
    private let green = Color(red: 0.19, green: 0.38, blue: 0.30)
    private let muted = Color(red: 0.41, green: 0.45, blue: 0.40)
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.bar.xaxis").foregroundStyle(green)
                Text("TU USO").font(.system(size: 11, weight: .bold, design: .rounded)).tracking(2)
                Spacer()
                Button(action: refresh) { Image(systemName: "arrow.clockwise") }.help("Actualizar límites")
                Button(action: quit) { Image(systemName: "xmark") }.help("Cerrar widget")
            }.buttonStyle(.plain)
            VStack(alignment: .leading, spacing: 12) {
                HStack { Text("Codex").font(.system(size: 20, weight: .semibold)); Spacer(); Text(store.snapshot?.plan?.capitalized ?? "Cuenta").font(.system(size: 11)).foregroundStyle(muted) }
                quota(store.snapshot?.primary, fallback: "Ventana actual")
                quota(store.snapshot?.secondary, fallback: "Ventana semanal")
            }
            Divider().overlay(Color.black.opacity(0.06))
            VStack(alignment: .leading, spacing: 7) {
                HStack { Text("ChatGPT · mensajes").font(.system(size: 13, weight: .semibold)); Spacer(); Text("Sin lectura").font(.system(size: 10)).foregroundStyle(muted) }
                Text("No hay un contador automático verificado para esta cuenta. No se estima a partir de Codex.")
                    .font(.system(size: 11)).foregroundStyle(muted).fixedSize(horizontal: false, vertical: true)
                Button("Abrir ChatGPT ↗") { NSWorkspace.shared.open(URL(string: "https://chatgpt.com/")!) }.buttonStyle(.plain).font(.system(size: 11, weight: .medium)).foregroundStyle(green)
            }
            HStack(alignment: .top, spacing: 6) {
                Circle().fill(store.connected ? green : Color.orange).frame(width: 5, height: 5).padding(.top, 4)
                VStack(alignment: .leading, spacing: 3) {
                    Text(store.message)
                    if let last = store.lastRead { Text("Última lectura: \(last.formatted(date: .omitted, time: .standard))") }
                }.font(.system(size: 10)).foregroundStyle(muted)
                Spacer(minLength: 0)
            }
        }.padding(20).foregroundStyle(ink)
            .frame(width: 324, height: 400, alignment: .topLeading).background(Color(red: 0.96, green: 0.95, blue: 0.91))
            .preferredColorScheme(.light)
    }
    @ViewBuilder private func quota(_ window: UsageWindow?, fallback: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(window?.title ?? fallback).font(.system(size: 12)).foregroundStyle(muted)
                Spacer()
                if let window = window { Text("\(Int(window.remaining.rounded())) %").font(.system(size: 20, weight: .semibold, design: .rounded)).monospacedDigit(); Text("restante").font(.system(size: 10)).foregroundStyle(muted) }
                else { Text("—").font(.system(size: 20)).foregroundStyle(muted) }
            }
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.black.opacity(0.07))
                    if let window = window { Capsule().fill(window.remaining <= 10 ? Color.red.opacity(0.8) : window.remaining <= 25 ? Color.orange : green).frame(width: max(0, geometry.size.width * window.remaining / 100)) }
                }
            }.frame(height: 5)
            if let reset = window?.reset { Text("Renueva \(reset.formatted(.dateTime.day().month(.abbreviated).hour().minute()))").font(.system(size: 10)).foregroundStyle(muted) }
            else { Text("Renovación no disponible").font(.system(size: 10)).foregroundStyle(muted) }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    var panel: NSPanel!
    var item: NSStatusItem!
    let store = UsageStore()
    var client: UsageClient!
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        client = UsageClient(store: store)
        let view = UsageView(store: store, refresh: { [weak self] in self?.client.refresh() }, quit: { NSApp.terminate(nil) })
        let host = NSHostingView(rootView: view)
        let size = host.fittingSize
        panel = NSPanel(contentRect: NSRect(origin: .zero, size: size), styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.contentView = host; panel.isFloatingPanel = true; panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        panel.isMovableByWindowBackground = true; panel.isReleasedWhenClosed = false
        panel.backgroundColor = .clear; panel.isOpaque = false; panel.hasShadow = true
        host.wantsLayer = true; host.layer?.cornerRadius = 18; host.layer?.masksToBounds = true
        placeTopRight(); panel.orderFrontRegardless()
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        item.button?.image = NSImage(systemSymbolName: "gauge.with.dots.needle.50percent", accessibilityDescription: "Tone Usage")
        let menu = NSMenu()
        menu.addItem(withTitle: "Mostrar arriba a la derecha", action: #selector(showPanel), keyEquivalent: "").target = self
        menu.addItem(withTitle: "Actualizar", action: #selector(update), keyEquivalent: "").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "Salir", action: #selector(quit), keyEquivalent: "q").target = self
        item.menu = menu
        NotificationCenter.default.addObserver(self, selector: #selector(screenChanged), name: NSApplication.didChangeScreenParametersNotification, object: nil)
        client.start()
    }
    func placeTopRight() {
        guard let screen = NSScreen.main ?? NSScreen.screens.first else { return }
        let frame = screen.visibleFrame
        panel.setFrameTopLeftPoint(NSPoint(x: frame.maxX-panel.frame.width-18, y: frame.maxY-18))
    }
    @objc func showPanel() { placeTopRight(); panel.orderFrontRegardless() }
    @objc func screenChanged() { placeTopRight() }
    @objc func update() { client.refresh() }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationWillTerminate(_ notification: Notification) { client.stop() }
}

#if WIDGET_PROBE
@main struct WidgetProbe {
    static func main() {
        let store = UsageStore(); let client = UsageClient(store: store)
        var reads = [Date]()
        let subscription = store.$lastRead.compactMap { $0 }.sink { reads.append($0) }
        client.start()
        let deadline = Date().addingTimeInterval(22)
        while reads.count < 2 && Date() < deadline { RunLoop.main.run(until: Date().addingTimeInterval(0.1)) }
        client.stop(); subscription.cancel()
        guard reads.count >= 2, let snapshot = store.snapshot, let primary = snapshot.primary, let secondary = snapshot.secondary else {
            print("Probe failed: no two valid reads"); exit(1)
        }
        print("Two live reads; interval=\(reads[1].timeIntervalSince(reads[0])); remaining=\(primary.remaining)/\(secondary.remaining)")
    }
}
#elseif WIDGET_RENDER
@main struct WidgetRender {
    static func main() {
        let app = NSApplication.shared; app.setActivationPolicy(.accessory)
        let store = UsageStore()
        store.received(UsageSnapshot.parse(["rateLimits":["limitId":"codex","planType":"plus","primary":["usedPercent":37,"windowDurationMins":300,"resetsAt":1792628274],"secondary":["usedPercent":28,"windowDurationMins":10080,"resetsAt":1793088012]]])!)
        let host = NSHostingView(rootView: UsageView(store:store,refresh:{},quit:{}))
        let size = host.fittingSize
        let window = NSWindow(contentRect:NSRect(origin:.zero,size:size),styleMask:[.borderless],backing:.buffered,defer:false)
        window.contentView = host
        host.layoutSubtreeIfNeeded()
        RunLoop.main.run(until:Date().addingTimeInterval(0.5))
        guard let bitmap = host.bitmapImageRepForCachingDisplay(in:host.bounds) else { exit(1) }
        host.cacheDisplay(in:host.bounds,to:bitmap)
        try! bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:"/private/tmp/tone-usage-preview.png"))
        print("Preview size: \(size)")
    }
}
#else
@main struct ToneUsageWidget {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate(); app.delegate = delegate
        withExtendedLifetime(delegate) { app.run() }
    }
}

#endif
