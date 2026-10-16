import SwiftUI
import WebKit
#if os(macOS)
import AppKit
#else
import UIKit
#endif

struct ContentView: View {
    @EnvironmentObject private var session: DashboardSession
    @Environment(\.scenePhase) private var scenePhase
    @State private var settings = false
    var body: some View {
        NavigationStack {
        VStack(spacing: 0) {
            if let error = session.lastError {
                Text(error).font(.callout).foregroundStyle(.red).padding(8).textSelection(.enabled)
            }
            if session.configured, let url = session.baseURL {
                DashboardWebView(session: session, baseURL: url).id(session.connectionID)
            } else {
                ContentUnavailableView("Tone Dashboard", systemImage: "server.rack", description: Text("Configura tu servidor para abrir la misma interfaz que utilizas en la web."))
            }
        }
        .toolbar {
            Button("Actualizar", systemImage:"arrow.clockwise") { session.lastError = nil; session.reload += 1 }.disabled(!session.configured)
            Button("Ajustes", systemImage:"gearshape") { settings = true }
        }
        .sheet(isPresented:$settings) { ConnectionSettings().environmentObject(session) }
        .onChange(of:scenePhase) { _, value in if value != .active { session.suspend += 1 } }
        .onDisappear { session.suspend += 1 }
        .frame(minWidth: 320, minHeight: 400)
        .navigationTitle("Tone Dashboard")
        }
    }
}

struct ConnectionSettings: View {
    @EnvironmentObject private var session: DashboardSession
    @Environment(\.dismiss) private var dismiss
    @State private var base = ""
    @State private var user = ""
    @State private var secret = ""
    var body: some View {
        Form {
            Text("Tone Dashboard · \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")").font(.headline)
            TextField("Servidor HTTPS",text:$base).autocorrectionDisabled()
            TextField("Usuario",text:$user).autocorrectionDisabled()
            SecureField("Contraseña",text:$secret)
            if let error = session.lastError { Text(error).foregroundStyle(.red) }
            Text("La contraseña permanece en el llavero. Web, Mac e iPhone comparten la interfaz del servidor.").font(.caption)
            HStack {
                Button("Cancelar") { secret = ""; dismiss() }
                Button("Guardar") {
                    guard session.save(base:base,user:user,secret:secret) else { return }
                    secret = ""
                    dismiss()
                }.buttonStyle(.borderedProminent)
            }
        }.padding().frame(minWidth:300,minHeight:300)
        .onAppear { base = session.baseURLString; user = session.username; secret = session.password }
        .onDisappear { secret = "" }
    }
}

@MainActor final class DashboardWebCoordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
    let session: DashboardSession
    let baseURL: URL
    private var lastReload: Int
    private var lastSuspend: Int
    init(session: DashboardSession,baseURL: URL) {
        self.session = session; self.baseURL = baseURL; lastReload = session.reload; lastSuspend = session.suspend
    }
    func configure(_ web: WKWebView) {
        web.navigationDelegate = self; web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
        web.load(DashboardOrigin.request(baseURL:baseURL))
    }
    func update(_ web: WKWebView) {
        if lastSuspend != session.suspend {
            lastSuspend = session.suspend
            web.evaluateJavaScript("window.ToneDashboard?.clearSensitiveState()",completionHandler:nil)
        }
        if lastReload != session.reload { lastReload = session.reload; web.reloadFromOrigin() }
    }
    func webView(_ webView: WKWebView,didReceive challenge: URLAuthenticationChallenge,completionHandler: @escaping (URLSession.AuthChallengeDisposition,URLCredential?) -> Void) {
        let space = challenge.protectionSpace
        if DashboardOrigin.acceptsChallenge(host:space.host,port:space.port,scheme:space.protocol,method:space.authenticationMethod,failures:challenge.previousFailureCount,baseURL:baseURL) {
            completionHandler(.useCredential,URLCredential(user:session.username,password:session.password,persistence:.none))
        } else { completionHandler(.performDefaultHandling,nil) }
    }
    func webView(_ webView: WKWebView,decidePolicyFor action: WKNavigationAction,decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if DashboardOrigin.trusted(url,baseURL:baseURL) || url.absoluteString == "about:blank" { decisionHandler(.allow); return }
        if action.navigationType == .linkActivated, ["https","http"].contains(url.scheme?.lowercased() ?? ""), url.user == nil, url.password == nil {
            #if os(macOS)
            NSWorkspace.shared.open(url)
            #else
            UIApplication.shared.open(url)
            #endif
        }
        decisionHandler(.cancel)
    }
    func webView(_ webView: WKWebView,createWebViewWith configuration: WKWebViewConfiguration,for action: WKNavigationAction,windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url, DashboardOrigin.trusted(url,baseURL:baseURL) { webView.load(action.request) }
        return nil
    }
    func webView(_ webView: WKWebView,didFailProvisionalNavigation navigation: WKNavigation!,withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled { session.lastError = "No se pudo conectar con el servidor. Comprueba la conexión y los ajustes." }
    }
    private func dialog(_ web: WKWebView,message: String,confirm: Bool,completion: @escaping (Bool) -> Void) {
        #if os(macOS)
        let alert = NSAlert(); alert.messageText = "Tone Dashboard"; alert.informativeText = message
        alert.addButton(withTitle:"Aceptar"); if confirm { alert.addButton(withTitle:"Cancelar") }
        if let window = web.window { alert.beginSheetModal(for:window) { completion($0 == .alertFirstButtonReturn) } }
        else { completion(false) }
        #else
        guard var controller = web.window?.rootViewController else { completion(false); return }
        while let presented = controller.presentedViewController { controller = presented }
        let alert = UIAlertController(title:"Tone Dashboard",message:message,preferredStyle:.alert)
        alert.addAction(UIAlertAction(title:"Aceptar",style:.default) { _ in completion(true) })
        if confirm { alert.addAction(UIAlertAction(title:"Cancelar",style:.cancel) { _ in completion(false) }) }
        controller.present(alert,animated:true)
        #endif
    }
    func webView(_ webView: WKWebView,runJavaScriptConfirmPanelWithMessage message: String,initiatedByFrame frame: WKFrameInfo,completionHandler: @escaping (Bool) -> Void) {
        guard let url = frame.request.url, DashboardOrigin.trusted(url,baseURL:baseURL) else { completionHandler(false); return }
        dialog(webView,message:message,confirm:true,completion:completionHandler)
    }
    func webView(_ webView: WKWebView,runJavaScriptAlertPanelWithMessage message: String,initiatedByFrame frame: WKFrameInfo,completionHandler: @escaping () -> Void) {
        guard let url = frame.request.url, DashboardOrigin.trusted(url,baseURL:baseURL) else { completionHandler(); return }
        dialog(webView,message:message,confirm:false) { _ in completionHandler() }
    }
    #if os(macOS)
    func webView(_ webView: WKWebView,runOpenPanelWith parameters: WKOpenPanelParameters,initiatedByFrame frame: WKFrameInfo,completionHandler: @escaping ([URL]?) -> Void) {
        guard let url = frame.request.url, DashboardOrigin.trusted(url,baseURL:baseURL),let window = webView.window else { completionHandler(nil); return }
        let panel = NSOpenPanel(); panel.allowsMultipleSelection = parameters.allowsMultipleSelection; panel.canChooseDirectories = parameters.allowsDirectories
        panel.beginSheetModal(for:window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }
    #endif
}

#if os(macOS)
struct DashboardWebView: NSViewRepresentable {
    @ObservedObject var session: DashboardSession
    let baseURL: URL
    func makeCoordinator() -> DashboardWebCoordinator { DashboardWebCoordinator(session:session,baseURL:baseURL) }
    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration(); config.websiteDataStore = session.websiteDataStore
        let web = WKWebView(frame:.zero,configuration:config); context.coordinator.configure(web); return web
    }
    func updateNSView(_ web: WKWebView,context: Context) { context.coordinator.update(web) }
}
#else
struct DashboardWebView: UIViewRepresentable {
    @ObservedObject var session: DashboardSession
    let baseURL: URL
    func makeCoordinator() -> DashboardWebCoordinator { DashboardWebCoordinator(session:session,baseURL:baseURL) }
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration(); config.websiteDataStore = session.websiteDataStore
        let web = WKWebView(frame:.zero,configuration:config); context.coordinator.configure(web); return web
    }
    func updateUIView(_ web: WKWebView,context: Context) { context.coordinator.update(web) }
}
#endif
