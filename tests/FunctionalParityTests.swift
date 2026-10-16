import Foundation

final class MockProtocol: URLProtocol, @unchecked Sendable {
    static var handler: (URLRequest) throws -> (Int, String) = { _ in (500, "{}") }
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        do {
            let (status, json) = try Self.handler(request)
            let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type":"application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: Data(json.utf8))
            client?.urlProtocolDidFinishLoading(self)
        } catch { client?.urlProtocol(self, didFailWithError: error) }
    }
    override func stopLoading() {}
}

@main
struct FunctionalParityTests {
    @MainActor static func main() async throws {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockProtocol.self]
        let api = APIClient(baseURL: URL(string: "https://dashboard.test")!, username: "test", password: "login-only", sessionConfiguration: configuration)
        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/deals/products")
            precondition(request.httpMethod == "POST")
            precondition(request.value(forHTTPHeaderField: "X-Dashboard-Action") == "write")
            return (200, "{\"ok\":true}")
        }
        let productReply = try await api.addTrackedProduct(ean: "0711719021247")
        precondition(productReply.ok == true)
        MockProtocol.handler = { _ in (400, "{\"error\":\"EAN inválido\"}") }
        do { _ = try await api.addTrackedProduct(ean: "bad"); preconditionFailure("Expected invalid EAN") }
        catch { precondition(error.localizedDescription == "EAN inválido") }
        let productJSON = #"{"available":true,"products":[{"ean":"0711719021247","name":"Producto"}],"active_offers":[{"ean":"0711719021247","family":"ean","price":14995}],"history":[],"events":[]}"#
        let productDeals = try JSONDecoder().decode(DealsResponse.self, from: Data(productJSON.utf8))
        precondition(productDeals.products?.first?.ean == "0711719021247")
        precondition(productDeals.activeOffers.first?.ean == productDeals.products?.first?.ean)
        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/deals/products/remove")
            precondition(request.httpMethod == "POST")
            precondition(request.value(forHTTPHeaderField: "X-Dashboard-Action") == "write")
            return (200, "{\"ok\":true,\"removed\":true}")
        }
        let removed = try await api.removeTrackedProduct(id: "ean:0711719021247")
        precondition(removed.ok == true)
        let trackingJSON = #"{"available":true,"products":[{"id":"ps5","ean":"","name":"PS5","family":"ps5"}],"inactive_products":[{"id":"switch2","ean":"","name":"Switch","family":"switch2"}],"active_offers":[],"history":[],"events":[]}"#
        let trackers = try JSONDecoder().decode(DealsResponse.self, from: Data(trackingJSON.utf8))
        precondition(trackers.products?.first?.id == "ps5")
        precondition(trackers.inactiveProducts?.first?.id == "switch2")
        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/deals/products/restore")
            precondition(request.httpMethod == "POST")
            return (200, "{\"ok\":true}")
        }
        let restored = try await api.restoreTrackedProduct(id: "ps5")
        precondition(restored.ok == true)
        let secret = "pair-only-password"
        let request = try api.request(path: "/api/orbit/pair-code", method: "POST", body: Data("{}".utf8), extraHeaders: ["X-Orbit-Action":"reveal-code", "X-Orbit-Pair-Password":secret])
        precondition(request.httpMethod == "POST")
        precondition(request.value(forHTTPHeaderField: "X-Dashboard-Action") == "write")
        precondition(request.url?.query == nil && !(request.url?.absoluteString.contains(secret) ?? true))
        precondition(String(data: request.httpBody!, encoding: .utf8) == "{}")
        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/orbit/pair-code")
            precondition(request.value(forHTTPHeaderField: "X-Orbit-Pair-Password") == secret)
            precondition(request.value(forHTTPHeaderField: "X-Orbit-Action") == "reveal-code")
            precondition(request.value(forHTTPHeaderField: "Authorization") == "Basic " + Data("test:login-only".utf8).base64EncodedString())
            return (200, "{\"code\":\"123456\",\"display_seconds\":60}")
        }
        let reply = try await api.revealOrbitCode(password: secret)
        precondition(reply.code == "123456")
        for status in [401, 429, 503] {
            MockProtocol.handler = { _ in (status, "{\"error\":\"Error controlado\"}") }
            do { _ = try await api.revealOrbitCode(password: secret); preconditionFailure("Expected HTTP failure") }
            catch { precondition((error as NSError).code == status && error.localizedDescription == "Error controlado") }
        }
        MockProtocol.handler = { _ in (200, "{\"code\":\"DO-NOT-LEAK\",\"display_seconds\":oops}") }
        do { _ = try await api.revealOrbitCode(password: secret); preconditionFailure("Expected JSON failure") }
        catch { precondition(!error.localizedDescription.contains("DO-NOT-LEAK")) }

        var waitSeconds = 0
        var expire: CheckedContinuation<Void, Error>?
        let state = OrbitCodeController(wait: { seconds in
            waitSeconds = seconds
            try await withCheckedThrowingContinuation { expire = $0 }
        })
        state.reveal { OrbitPairCodeResponse(code: "123456", display_seconds: 600) }
        try await eventually { state.code != nil && expire != nil }
        precondition(waitSeconds == 60 && !state.busy)
        expire?.resume(); expire = nil
        try await eventually { state.code == nil }

        var late: CheckedContinuation<OrbitPairCodeResponse, Error>?
        state.reveal { try await withCheckedThrowingContinuation { late = $0 } }
        try await eventually { late != nil }
        state.clear() // close/background/account change use this same operation
        precondition(!state.busy && state.code == nil && state.error == nil)
        late?.resume(returning: OrbitPairCodeResponse(code: "stale", display_seconds: 60))
        try await Task.sleep(for: .milliseconds(20))
        precondition(state.code == nil)
        state.reveal { throw URLError(.notConnectedToInternet) }
        try await eventually { state.error != nil }
        state.reveal { OrbitPairCodeResponse(code: "", display_seconds: 60) }
        try await eventually { state.error != nil && !state.busy }
        precondition(state.code == nil)
        state.clear()

        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/orbit/start")
            precondition(request.value(forHTTPHeaderField: "X-Orbit-Action") == "start")
            precondition(request.value(forHTTPHeaderField: "X-Orbit-Control-Password") == "start-only-password")
            precondition(request.value(forHTTPHeaderField: "X-Orbit-Pair-Password") == nil)
            return (200, "{\"running\":true,\"message\":\"Arranque solicitado\"}")
        }
        _ = try await api.startOrbit(controlPassword: "start-only-password")
        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/download" && request.httpMethod == "POST")
            precondition(request.value(forHTTPHeaderField: "X-Dashboard-Action") == "write")
            precondition(request.value(forHTTPHeaderField: "X-Orbit-Pair-Password") == nil)
            return (200, "{\"ok\":true,\"request_id\":1}")
        }
        _ = try await api.queueDownload(url: "https://download.test/file.zip")
        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/torrent")
            precondition(request.value(forHTTPHeaderField: "Content-Type") == "application/x-bittorrent")
            precondition(request.value(forHTTPHeaderField: "X-Torrent-Filename")?.removingPercentEncoding == "prueba ñ.torrent")
            return (200, "{\"ok\":true,\"name\":\"prueba\"}")
        }
        _ = try await api.uploadTorrent(data: Data("test".utf8), filename: "prueba ñ.torrent")

        let suite = "ToneParityTests-" + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set("https://dashboard.test", forKey: "baseURL")
        defaults.set("test", forKey: "username")
        let session = DashboardSession(defaults: defaults, passwordLoader: { _ in "login-only" }, sessionConfiguration: configuration)
        session.selectedTab = "Ofertas"
        session.logLines = 1000
        MockProtocol.handler = { request in
            precondition(request.url?.path == "/api/deals" && request.url?.query == "lines=1000")
            return (200, "{\"available\":true,\"active_offers\":[],\"history\":[],\"events\":[{\"name\":\"Tienda\",\"level\":\"error\",\"detail\":\"Prueba\",\"created_iso\":null}],\"log\":\"log de prueba\"}")
        }
        await session.refreshAll()
        precondition(session.deals?.events.count == 1 && session.lastError == nil && session.lastUpdated != nil)
        MockProtocol.handler = { _ in (503, "{\"error\":\"Servicio no disponible\"}") }
        await session.refreshAll()
        precondition(session.lastError == "Servicio no disponible")
        session.selectedTab = "Logs"
        MockProtocol.handler = { request in
            precondition(request.url?.query == "lines=1000")
            return (200, "{\"logs\":{\"organizer_out\":\"hola\",\"nuevo_servicio\":\"registro\"}}")
        }
        await session.refreshAll()
        precondition(session.logs["nuevo_servicio"] == "registro" && session.lastError == nil)
        MockProtocol.handler = { _ in
            Thread.sleep(forTimeInterval: 0.05)
            return (200, "{\"logs\":{\"stale\":\"must not appear\"}}")
        }
        let staleRefresh = Task { await session.refreshAll() }
        try await Task.sleep(for: .milliseconds(10))
        session.username = "another-account"
        session.clearConnectionData()
        await staleRefresh.value
        precondition(session.logs.isEmpty && session.lastUpdated == nil)
        session.username = "test"
        session.selectedTab = "Orbit"
        MockProtocol.handler = { _ in (200, "{\"running\":true,\"can_start\":true,\"start_configured\":true,\"pair_code_available\":true}") }
        await session.refreshAll()
        precondition(session.orbitStatus?.pair_code_available == true)
        precondition(durationString(3661) == "1 h 1 min")
        precondition(durationString(-1) == "—")
        precondition(safeOfferURL("javascript:alert(1)") == nil)
        precondition(safeOfferURL("file:///etc/passwd") == nil)
        precondition(safeOfferURL("https://shop.test/product") != nil)
        precondition(availabilityLabel("preorder") == "Preventa / reserva")
        precondition(localizedStatus("quarantined") == "Cuarentena")
        print("Functional parity checks passed: protected requests, HTTP errors, secret redaction, expiry, late cancellation, retries, deals/logs/status and formatters")
    }

    @MainActor static func eventually(_ condition: () -> Bool) async throws {
        for _ in 0..<100 {
            if condition() { return }
            try await Task.sleep(for: .milliseconds(5))
        }
        preconditionFailure("Timed out waiting for async state")
    }
}
