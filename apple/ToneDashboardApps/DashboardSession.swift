import Foundation
import Combine

@MainActor
final class DashboardSession: ObservableObject {
    @Published var dashboard: DashboardResponse?
    @Published var deals: DealsResponse?
    @Published var logs: [String: String] = [:]
    @Published var logLines = 300
    @Published var submittingDownload = false
    @Published var submittingTorrent = false
    @Published var isLoading = false
    @Published var lastError: String?
    @Published var lastUpdated: Date?
    @Published var toast: String?
    @Published var orbitStatus: OrbitStatus?
    @Published var orbitError: String?

    @Published var baseURLString: String
    @Published var username: String
    @Published var password: String

    @Published var selectedTab = "Inicio"
    var isActive = true
    private var refreshing = false

    private var refreshTask: Task<Void, Never>?
    private var persistedUsername: String

    private let defaults: UserDefaults
    private let sessionConfiguration: URLSessionConfiguration

    init(defaults: UserDefaults = .standard,
         passwordLoader: (String) -> String = KeychainStore.password,
         sessionConfiguration: URLSessionConfiguration = .ephemeral) {
        self.defaults = defaults
        self.sessionConfiguration = sessionConfiguration
        let savedBaseURL = defaults.string(forKey: "baseURL") ?? ""
        let savedUsername = defaults.string(forKey: "username") ?? ""
        let savedPassword = passwordLoader(savedUsername)

        baseURLString = savedBaseURL
        username = savedUsername
        password = savedPassword
        persistedUsername = savedUsername
    }

    var configured: Bool {
        guard let url = URL(string: baseURLString),
              url.scheme?.lowercased() == "https",
              url.host != nil, url.user == nil, url.password == nil else {
            return false
        }
        return !username.isEmpty && !password.isEmpty
    }

    var client: APIClient? {
        guard configured, let url = URL(string: baseURLString) else { return nil }
        return APIClient(baseURL: url, username: username, password: password, sessionConfiguration: sessionConfiguration)
    }

    func clearConnectionData() {
        dashboard = nil; deals = nil; logs = [:]
        orbitStatus = nil; orbitError = nil; lastError = nil
        lastUpdated = nil; toast = nil
    }

    private func connectionMatches(_ client: APIClient) -> Bool {
        client.baseURL == URL(string: baseURLString) && client.username == username && client.password == password
    }

    func bootstrap() async {
        if configured { await refreshAll() }
        refreshTask?.cancel()
        refreshTask = Task { [weak self] in
            while !Task.isCancelled {
                do { try await Task.sleep(for: .seconds(12)) }
                catch { return }
                guard let self, self.configured, self.isActive else { continue }
                await self.refreshAll(silent: true)
            }
        }
    }

    func saveSettings() async {
        baseURLString = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        username = username.trimmingCharacters(in: .whitespacesAndNewlines)
        defaults.set(baseURLString, forKey: "baseURL")
        defaults.set(username, forKey: "username")

        if persistedUsername != username {
            KeychainStore.deletePassword(account: persistedUsername)
        }
        KeychainStore.savePassword(password, account: username)
        persistedUsername = username

        clearConnectionData()
        guard let client else {
            lastError = "Configura una URL HTTPS válida, usuario y contraseña en Ajustes."
            return
        }

        isLoading = true
        defer { isLoading = false }
        do {
            let fetched = try await client.dashboard()
            guard connectionMatches(client) else { return }
            dashboard = fetched
            lastUpdated = Date()
            lastError = nil
            toast = "Conexión correcta"
            await refreshSecondary(client: client)
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
        }
    }

    func refreshAll(silent: Bool = false) async {
        guard !refreshing else { return }
        refreshing = true
        defer { refreshing = false }
        if selectedTab == "Ajustes" { return }
        if selectedTab == "Orbit" {
            await refreshOrbitStatus()
            return
        }
        guard let client else {
            if !silent { lastError = "Configura una URL HTTPS válida, usuario y contraseña en Ajustes." }
            return
        }
        if !silent { isLoading = true }
        defer { if !silent { isLoading = false } }
        if selectedTab == "Ofertas" || selectedTab == "Logs" {
            await refreshSecondary(client: client)
            return
        }

        do {
            let fetched = try await client.dashboard()
            guard connectionMatches(client) else { return }
            dashboard = fetched
            lastUpdated = Date()
            lastError = nil
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
            return
        }

        await refreshSecondary(client: client)
    }

    private func refreshSecondary(client: APIClient) async {
        do {
            if selectedTab == "Ofertas" {
                let fetched = try await client.deals(lines: logLines)
                guard connectionMatches(client) else { return }
                deals = fetched
            }
            if selectedTab == "Logs" {
                let fetched = try await client.logs(lines: logLines)
                guard connectionMatches(client) else { return }
                logs = fetched.logs
            }
            lastError = nil
            lastUpdated = Date()
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
        }
    }

    func addTrackedProduct(ean: String) async -> Bool {
        guard let client else { return false }
        do {
            _ = try await client.addTrackedProduct(ean: ean)
            guard connectionMatches(client) else { return false }
            let fetched = try await client.deals(lines: logLines)
            guard connectionMatches(client) else { return false }
            deals = fetched
            lastError = nil
            return true
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
            return false
        }
    }

    func removeTrackedProduct(id: String) async -> Bool {
        guard let client else { return false }
        do {
            _ = try await client.removeTrackedProduct(id: id)
            let fetched = try await client.deals(lines: logLines)
            guard connectionMatches(client) else { return false }
            deals = fetched
            lastError = nil
            return true
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
            return false
        }
    }

    func restoreTrackedProduct(id: String) async -> Bool {
        guard let client else { return false }
        do {
            _ = try await client.restoreTrackedProduct(id: id)
            let fetched = try await client.deals(lines: logLines)
            guard connectionMatches(client) else { return false }
            deals = fetched
            lastError = nil
            return true
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
            return false
        }
    }

    func queueDownload(_ url: String) async -> Bool {
        guard let client, !submittingDownload else { return false }
        submittingDownload = true
        defer { submittingDownload = false }
        do {
            _ = try await client.queueDownload(url: url.trimmingCharacters(in: .whitespacesAndNewlines))
            guard connectionMatches(client) else { return false }
            lastError = nil
            toast = "Descarga añadida a la cola"
            await refreshAll(silent: true)
            return true
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
            return false
        }
    }

    func uploadTorrent(url: URL) async -> Bool {
        guard let client, !submittingTorrent else { return false }
        submittingTorrent = true
        defer { submittingTorrent = false }
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        do {
            let data = try Data(contentsOf: url)
            let response = try await client.uploadTorrent(data: data, filename: url.lastPathComponent)
            guard connectionMatches(client) else { return false }
            lastError = nil
            toast = "Torrent añadido: \(response.name ?? url.lastPathComponent)"
            await refreshAll(silent: true)
            return true
        } catch {
            if connectionMatches(client) { lastError = error.localizedDescription }
            return false
        }
    }
    func refreshOrbitStatus() async {
        guard let client else { orbitStatus = nil; return }
        do {
            let fetched = try await client.orbitStatus()
            guard connectionMatches(client) else { return }
            orbitStatus = fetched
            orbitError = nil
        } catch {
            if connectionMatches(client) { orbitError = error.localizedDescription }
        }
    }

    func startOrbit(controlPassword: String) async -> Bool {
        guard let client, controlPassword.count >= 12 else {
            orbitError = "La contraseña de control debe tener al menos 12 caracteres."
            return false
        }
        do {
            let reply = try await client.startOrbit(controlPassword: controlPassword)
            guard connectionMatches(client) else { return false }
            toast = reply.message ?? "Solicitud de arranque enviada"
            orbitError = nil
            await refreshOrbitStatus()
            return true
        } catch {
            if connectionMatches(client) { orbitError = error.localizedDescription }
            return false
        }
    }

}
