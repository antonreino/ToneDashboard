import Foundation
import Combine
import Security
import WebKit

@MainActor final class DashboardSession: ObservableObject {
    @Published var baseURLString: String
    @Published var username: String
    @Published var password: String
    @Published var lastError: String?
    @Published var connectionID = UUID()
    @Published var reload = 0
    @Published var suspend = 0
    private let defaults: UserDefaults
    init(defaults: UserDefaults = .standard, passwordLoader: (String) -> String = KeychainStore.password) {
        self.defaults = defaults
        baseURLString = defaults.string(forKey: "baseURL") ?? ""
        let savedUser = defaults.string(forKey: "username") ?? ""
        username = savedUser
        password = passwordLoader(savedUser)
        if defaults.string(forKey:"legacyWebAccount") == nil, let url = URL(string:baseURLString), DashboardOrigin.valid(url), !username.isEmpty {
            defaults.set(Self.accountKey(url:url,user:username),forKey:"legacyWebAccount")
        }
    }
    var baseURL: URL? {
        guard let url = URL(string: baseURLString), DashboardOrigin.valid(url) else { return nil }
        return url
    }
    static func accountKey(url: URL,user: String) -> String { "\(url.host!.lowercased()):\(url.port ?? 443)|\(user)" }
    var usesLegacyWebStore: Bool {
        guard let url = baseURL else { return false }
        return defaults.string(forKey:"legacyWebAccount") == Self.accountKey(url:url,user:username)
    }
    var websiteDataStore: WKWebsiteDataStore {
        if usesLegacyWebStore { return .default() }
        guard let url = baseURL else { return .nonPersistent() }
        let key = "webStore." + Self.accountKey(url:url,user:username)
        let identifier = defaults.string(forKey:key).flatMap(UUID.init(uuidString:)) ?? UUID()
        defaults.set(identifier.uuidString,forKey:key)
        return WKWebsiteDataStore(forIdentifier:identifier)
    }
    var configured: Bool { baseURL != nil && !username.isEmpty && !password.isEmpty }
    func save(base: String, user: String, secret: String) -> Bool {
        let base = base.trimmingCharacters(in: .whitespacesAndNewlines)
        let user = user.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: base), DashboardOrigin.valid(url), !user.isEmpty, !secret.isEmpty else {
            lastError = "Introduce una URL HTTPS válida, usuario y contraseña."; return false
        }
        guard KeychainStore.savePassword(secret, account: user) == errSecSuccess else {
            lastError = "No se pudo guardar la contraseña en el llavero."; return false
        }
        defaults.set(base, forKey: "baseURL"); defaults.set(user, forKey: "username")
        baseURLString = base; username = user; password = secret; lastError = nil
        connectionID = UUID()
        return true
    }
}
