import Foundation

@MainActor
final class DashboardSession: ObservableObject {
    @Published var dashboard: DashboardResponse?
    @Published var deals: DealsResponse?
    @Published var logs: [String: String] = [:]
    @Published var isLoading = false
    @Published var lastError: String?
    @Published var lastUpdated: Date?
    @Published var toast: String?

    @Published var baseURLString: String
    @Published var username: String
    @Published var password: String

    private var refreshTask: Task<Void, Never>?
    private var persistedUsername: String

    init() {
        let defaults = UserDefaults.standard
        let savedBaseURL = defaults.string(forKey: "baseURL") ?? ""
        let savedUsername = defaults.string(forKey: "username") ?? ""
        let savedPassword = KeychainStore.password(account: savedUsername)

        baseURLString = savedBaseURL
        username = savedUsername
        password = savedPassword
        persistedUsername = savedUsername
    }

    var configured: Bool {
        guard let url = URL(string: baseURLString),
              url.scheme?.lowercased() == "https",
              url.host != nil else {
            return false
        }
        return !username.isEmpty && !password.isEmpty
    }

    var client: APIClient? {
        guard configured, let url = URL(string: baseURLString) else { return nil }
        return APIClient(baseURL: url, username: username, password: password)
    }

    func bootstrap() async {
        if configured { await refreshAll() }
        refreshTask?.cancel()
        refreshTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                guard let self, self.configured else { continue }
                await self.refreshAll(silent: true)
            }
        }
    }

    func saveSettings() async {
        baseURLString = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        username = username.trimmingCharacters(in: .whitespacesAndNewlines)
        UserDefaults.standard.set(baseURLString, forKey: "baseURL")
        UserDefaults.standard.set(username, forKey: "username")

        if persistedUsername != username {
            KeychainStore.deletePassword(account: persistedUsername)
        }
        KeychainStore.savePassword(password, account: username)
        persistedUsername = username

        guard let client else {
            lastError = "Configura una URL HTTPS válida, usuario y contraseña en Ajustes."
            return
        }

        isLoading = true
        defer { isLoading = false }
        do {
            dashboard = try await client.dashboard()
            lastUpdated = Date()
            lastError = nil
            toast = "Conexión correcta"
            await refreshSecondary(client: client)
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshAll(silent: Bool = false) async {
        guard let client else {
            if !silent { lastError = "Configura una URL HTTPS válida, usuario y contraseña en Ajustes." }
            return
        }
        if !silent { isLoading = true }
        defer { if !silent { isLoading = false } }

        do {
            dashboard = try await client.dashboard()
            lastUpdated = Date()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
            return
        }

        await refreshSecondary(client: client)
    }

    private func refreshSecondary(client: APIClient) async {
        async let dealsResult: DealsResponse? = try? client.deals()
        async let logsResult: LogResponse? = try? client.logs()

        if let fetchedDeals = await dealsResult {
            deals = fetchedDeals
        }
        if let fetchedLogs = await logsResult {
            logs = fetchedLogs.logs
        }
    }

    func queueDownload(_ url: String) async -> Bool {
        guard let client else { return false }
        do {
            _ = try await client.queueDownload(url: url)
            toast = "Descarga añadida a la cola"
            await refreshAll(silent: true)
            return true
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }

    func uploadTorrent(url: URL) async -> Bool {
        guard let client else { return false }
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        do {
            let data = try Data(contentsOf: url)
            let response = try await client.uploadTorrent(data: data, filename: url.lastPathComponent)
            toast = "Torrent añadido: \(response.name ?? url.lastPathComponent)"
            await refreshAll(silent: true)
            return true
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }
}
