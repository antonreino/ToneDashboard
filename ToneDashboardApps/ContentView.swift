import SwiftUI
import WebKit

struct ContentView: View {
    @EnvironmentObject private var session: DashboardSession

    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack {
            DashboardBackground()
            TabView(selection: $session.selectedTab) {
                NavigationStack { OverviewView() }
                    .tabItem { Label("Inicio", systemImage: "house.fill") }
                    .tag("Inicio")
                NavigationStack { DownloadsView() }
                    .tabItem { Label("Descargas", systemImage: "arrow.down.circle.fill") }
                    .tag("Descargas")
                NavigationStack { OrbitZeroView() }
                    .tabItem { Label("Orbit", systemImage: "gamecontroller.fill") }
                    .tag("Orbit")
                NavigationStack { ActivityView() }
                    .tabItem { Label("Actividad", systemImage: "clock.arrow.circlepath") }
                    .tag("Actividad")
                NavigationStack { DealsView() }
                    .tabItem { Label("Ofertas", systemImage: "tag.fill") }
                    .tag("Ofertas")
#if os(macOS)
                NavigationStack { LogsView() }
                    .tabItem { Label("Logs", systemImage: "terminal.fill") }
                    .tag("Logs")
                NavigationStack { SettingsView() }
                    .tabItem { Label("Ajustes", systemImage: "gearshape.fill") }
                    .tag("Ajustes")
#else
                LogsView()
                    .tabItem { Label("Logs", systemImage: "terminal.fill") }
                    .tag("Logs")
                SettingsView()
                    .tabItem { Label("Ajustes", systemImage: "gearshape.fill") }
                    .tag("Ajustes")
#endif
            }
            .tint(DashboardPalette.accent)
            .onChange(of: session.selectedTab) { _, _ in
                Task { await session.refreshAll() }
            }
            .onChange(of: scenePhase) { _, phase in
                session.isActive = phase == .active
                if phase == .active { Task { await session.refreshAll() } }
            }
        }
        .preferredColorScheme(.dark)
        .overlay(alignment: .top) {
            if let toast = session.toast {
                Text(toast)
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(DashboardPalette.text)
                    .padding(.horizontal, 14).padding(.vertical, 9)
                    .background(DashboardPalette.panel, in: Capsule())
                    .overlay { Capsule().stroke(DashboardPalette.border, lineWidth: 1) }
                    .padding(.top, 8)
                    .onAppear {
                        Task {
                            try? await Task.sleep(for: .seconds(3))
                            await MainActor.run { session.toast = nil }
                        }
                    }
            }
        }
    }
}


// MARK: - Orbit Zero en la app nativa (Mac / iOS / iPadOS)
// Se usa el proxy SAME-ORIGIN de ToneDashboard; no expone el puerto 34179
// ni accede a las ventanas o al escritorio del Mac.
struct OrbitZeroView: View {
    @EnvironmentObject private var session: DashboardSession
    @State private var showStartDialog = false
    @State private var controlPassword = ""
    @State private var starting = false
    @State private var reloadIdentity = UUID()

    @State private var showPairCode = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Orbit Zero").font(.headline)
                    Text(session.orbitStatus?.running == true ? "Servicio conectado" : "Servicio sin confirmar")
                        .font(.caption)
                        .foregroundStyle(session.orbitStatus?.running == true ? Color.green : Color.secondary)
                }
                Spacer()
                Button("Comprobar", systemImage: "arrow.clockwise") {
                    Task { await session.refreshOrbitStatus() }
                }
                .buttonStyle(.bordered)
                if session.orbitStatus?.running == false && session.orbitStatus?.can_start == true {
                    Button("Iniciar Orbit", systemImage: "play.fill") {
                        showStartDialog = true
                    }
                    .buttonStyle(.borderedProminent)
                }
                Button("Ver código", systemImage: "key.fill") { showPairCode = true }
                    .buttonStyle(.bordered)
                Button("Recargar", systemImage: "arrow.clockwise.circle") {
                    reloadIdentity = UUID()
                }
                .buttonStyle(.bordered)
            }
            .font(.callout)
            if let error = session.orbitError {
                Text(error).font(.caption).foregroundStyle(.orange)
            }
            if let base = session.client?.baseURL,
               base.scheme?.lowercased() == "https" {
                OrbitWebView(baseURL: base,
                             username: session.username,
                             password: session.password)
                    .id(reloadIdentity)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                ContentUnavailableView("Configura ToneDashboard", systemImage: "lock.shield",
                    description: Text("Introduce la URL HTTPS y las credenciales en Ajustes."))
            }
            Text("Las verificaciones externas de algunos proveedores siguen realizándose en el Mac. Esta pestaña no da acceso remoto al escritorio. Para acceder fuera de casa usa VPN y HTTPS.")
                .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(12)
        .navigationTitle("Orbit Zero")
        .task { await session.refreshOrbitStatus() }
        .sheet(isPresented: $showPairCode) { OrbitPairCodeSheet() }
        .alert("Arrancar Orbit Zero", isPresented: $showStartDialog) {
            SecureField("Contraseña adicional", text: $controlPassword)
            Button("Cancelar", role: .cancel) { controlPassword = "" }
            Button("Iniciar") {
                let secret = controlPassword
                controlPassword = ""
                starting = true
                Task {
                    let success = await session.startOrbit(controlPassword: secret)
                    if success { reloadIdentity = UUID() }
                    starting = false
                }
            }
            .disabled(starting || controlPassword.count < 12)
        } message: {
            Text("Se utiliza la contraseña adicional configurada en el servidor. No se guarda en el iPhone ni en el Mac.")
        }
    }
}

struct OrbitWebView: View {
    let baseURL: URL
    let username: String
    let password: String

    var body: some View {
        #if os(macOS)
        OrbitWebKitMac(baseURL: baseURL, username: username, password: password)
        #else
        OrbitWebKitMobile(baseURL: baseURL, username: username, password: password)
        #endif
    }
}

// Datos compartidos por las dos plataformas. Jamás se envían credenciales
// a hosts externos ni se aceptan certificados TLS no confiables.
final class OrbitWebCoordinator: NSObject, WKNavigationDelegate {
    private var baseURL: URL
    private var username: String
    private var password: String

    init(baseURL: URL, username: String, password: String) {
        self.baseURL = baseURL
        self.username = username
        self.password = password
    }

    func update(_ webView: WKWebView, baseURL: URL, username: String, password: String) {
        guard self.baseURL != baseURL || self.username != username || self.password != password else { return }
        webView.stopLoading()
        self.baseURL = baseURL
        self.username = username
        self.password = password
        webView.load(orbitRequest(baseURL: baseURL, username: username, password: password))
    }

    func webView(_ webView: WKWebView, didReceive challenge: URLAuthenticationChallenge,
                 completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        let space = challenge.protectionSpace
        guard challenge.previousFailureCount == 0,
              space.authenticationMethod == NSURLAuthenticationMethodHTTPBasic,
              space.protocol?.lowercased() == "https",
              space.host.caseInsensitiveCompare(baseURL.host ?? "") == .orderedSame,
              space.port == (baseURL.port ?? 443) else {
            completionHandler(.performDefaultHandling, nil)
            return
        }
        completionHandler(.useCredential, URLCredential(user: username, password: password,
                                                       persistence: .none))
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel); return
        }
        // No permitir que Orbit navegue a otros servidores desde la app.
        let trusted = url.scheme?.lowercased() == "https" &&
            url.host?.caseInsensitiveCompare(baseURL.host ?? "") == .orderedSame &&
            (url.port ?? 443) == (baseURL.port ?? 443)
        decisionHandler(trusted || url.scheme == "about" ? .allow : .cancel)
    }
}

func orbitRequest(baseURL: URL, username: String, password: String) -> URLRequest {
    var request = URLRequest(url: URL(string: "/orbit-bridge/zero/", relativeTo: baseURL)!.absoluteURL)
    request.cachePolicy = .reloadIgnoringLocalCacheData
    request.setValue("Basic " + Data("\(username):\(password)".utf8).base64EncodedString(),
                     forHTTPHeaderField: "Authorization")
    return request
}

#if os(macOS)
struct OrbitWebKitMac: NSViewRepresentable {
    let baseURL: URL
    let username: String
    let password: String

    func makeCoordinator() -> OrbitWebCoordinator {
        OrbitWebCoordinator(baseURL: baseURL, username: username, password: password)
    }
    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = context.coordinator
        web.load(orbitRequest(baseURL: baseURL, username: username, password: password))
        return web
    }
    func updateNSView(_ nsView: WKWebView, context: Context) {
        context.coordinator.update(nsView, baseURL: baseURL, username: username, password: password)
    }
}
#else
struct OrbitWebKitMobile: UIViewRepresentable {
    let baseURL: URL
    let username: String
    let password: String

    func makeCoordinator() -> OrbitWebCoordinator {
        OrbitWebCoordinator(baseURL: baseURL, username: username, password: password)
    }
    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = context.coordinator
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.load(orbitRequest(baseURL: baseURL, username: username, password: password))
        return web
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {
        context.coordinator.update(uiView, baseURL: baseURL, username: username, password: password)
    }
}
#endif

struct OrbitPairCodeSheet: View {
    @EnvironmentObject private var session: DashboardSession
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var password = ""
    @State private var code: String?
    @State private var error: String?
    @State private var busy = false
    @State private var request: Task<Void, Never>?
    @State private var expiry: Task<Void, Never>?

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Código de Orbit").font(.title2)
            Text("Introduce la contraseña para consultar el código vigente del Mac. Se ocultará en 60 segundos.")
                .font(.callout)
            if let code {
                Text(code).font(.system(size: 36, weight: .bold, design: .monospaced))
                    .privacySensitive()
            } else {
                SecureField("Contraseña para mostrar el código", text: $password)
                    .onSubmit { reveal() }
                if let error { Text(error).foregroundStyle(.orange).font(.caption) }
            }
            HStack {
                Button("Cerrar") { clear(); dismiss() }
                Spacer()
                if code == nil {
                    Button(busy ? "Consultando…" : "Mostrar código") { reveal() }
                        .disabled(busy || password.count < 12)
                }
            }
        }
        .padding(24).frame(minWidth: 300, idealWidth: 420)
        .onDisappear { clear() }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active { clear(); dismiss() }
        }
        .onChange(of: session.baseURLString) { _, _ in clear(); dismiss() }
        .onChange(of: session.username) { _, _ in clear(); dismiss() }
        .onChange(of: session.password) { _, _ in clear(); dismiss() }
    }

    private func reveal() {
        guard !busy, let client = session.client else { return }
        let secret = password
        password = ""; code = nil; error = nil; busy = true
        request = Task { @MainActor in
            defer { busy = false }
            do {
                let result = try await client.revealOrbitCode(password: secret)
                guard !Task.isCancelled else { return }
                code = result.code
                expiry = Task { @MainActor in
                    do { try await Task.sleep(for: .seconds(60)) } catch { return }
                    clear(); dismiss()
                }
            } catch {
                if !Task.isCancelled { self.error = error.localizedDescription }
            }
        }
    }

    private func clear() {
        request?.cancel(); expiry?.cancel()
        password = ""; code = nil; error = nil
    }
}
