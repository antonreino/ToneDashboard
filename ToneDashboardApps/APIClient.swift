import Foundation

// Keep credentials and action passwords inside the configured HTTPS origin.
final class DashboardRedirectGuard: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    let baseURL: URL
    init(baseURL: URL) { self.baseURL = baseURL }

    static func trusted(_ url: URL, baseURL: URL) -> Bool {
        url.scheme?.lowercased() == "https" && baseURL.scheme?.lowercased() == "https" &&
        url.host != nil && url.host?.lowercased() == baseURL.host?.lowercased() &&
        (url.port ?? 443) == (baseURL.port ?? 443) && url.user == nil && url.password == nil
    }

    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        guard let url = request.url, Self.trusted(url, baseURL: baseURL),
              task.originalRequest?.httpMethod == "GET" else {
            completionHandler(nil); return
        }
        completionHandler(request)
    }
}

struct APIClient {
    var baseURL: URL
    var username: String
    var password: String
    var sessionConfiguration: URLSessionConfiguration = .ephemeral

    private var authHeader: String {
        Data("\(username):\(password)".utf8).base64EncodedString()
    }

    func request(path: String, method: String = "GET", body: Data? = nil, contentType: String? = nil, extraHeaders: [String: String] = [:]) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL,
              DashboardRedirectGuard.trusted(url, baseURL: baseURL),
              baseURL.user == nil, baseURL.password == nil else {
            throw URLError(.badURL)
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = 30
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.setValue("Basic \(authHeader)", forHTTPHeaderField: "Authorization")
        if let contentType { req.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        extraHeaders.forEach { req.setValue($1, forHTTPHeaderField: $0) }
        if method != "GET" { req.setValue("write", forHTTPHeaderField: "X-Dashboard-Action") }
        req.httpBody = body
        return req
    }

    private func execute<T: Decodable>(_ request: URLRequest, as type: T.Type) async throws -> T {
        let session = URLSession(configuration: sessionConfiguration,
                                 delegate: DashboardRedirectGuard(baseURL: baseURL), delegateQueue: nil)
        defer { session.finishTasksAndInvalidate() }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard (200..<300).contains(http.statusCode) else {
            if let ack = try? JSONDecoder().decode(APIAck.self, from: data), let error = ack.error {
                throw NSError(domain: "ToneDashboardApps", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: error])
            }
            if http.statusCode == 401 {
                throw NSError(domain: "ToneDashboardApps", code: 401, userInfo: [NSLocalizedDescriptionKey: "Usuario o contraseña incorrectos"])
            }
            throw NSError(domain: "ToneDashboardApps", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: "HTTP \(http.statusCode)"])
        }
        do {
            return try JSONDecoder().decode(type, from: data)
        } catch let DecodingError.typeMismatch(expected, context) {
            let path = context.codingPath.map(\.stringValue).joined(separator: ".")
            throw NSError(
                domain: "ToneDashboardApps",
                code: -2,
                userInfo: [NSLocalizedDescriptionKey: "Formato inesperado en \(path.isEmpty ? "respuesta" : path): se esperaba \(expected). \(context.debugDescription)"]
            )
        } catch let DecodingError.valueNotFound(expected, context) {
            let path = context.codingPath.map(\.stringValue).joined(separator: ".")
            throw NSError(
                domain: "ToneDashboardApps",
                code: -3,
                userInfo: [NSLocalizedDescriptionKey: "Valor ausente en \(path.isEmpty ? "respuesta" : path): \(expected). \(context.debugDescription)"]
            )
        } catch let DecodingError.keyNotFound(key, context) {
            let parent = context.codingPath.map(\.stringValue).joined(separator: ".")
            let path = parent.isEmpty ? key.stringValue : "\(parent).\(key.stringValue)"
            throw NSError(
                domain: "ToneDashboardApps",
                code: -4,
                userInfo: [NSLocalizedDescriptionKey: "Falta el campo \(path) en la respuesta del servidor."]
            )
        } catch let DecodingError.dataCorrupted(context) {
            let path = context.codingPath.map(\.stringValue).joined(separator: ".")
            throw NSError(
                domain: "ToneDashboardApps",
                code: -5,
                userInfo: [NSLocalizedDescriptionKey: "JSON no válido en \(path.isEmpty ? "respuesta" : path). \(context.debugDescription)"]
            )
        } catch {
            throw NSError(
                domain: "ToneDashboardApps",
                code: -6,
                userInfo: [NSLocalizedDescriptionKey: "No se pudo interpretar la respuesta del servidor: \(error.localizedDescription)"]
            )
        }
    }

    func dashboard() async throws -> DashboardResponse {
        try await execute(try request(path: "/api/dashboard"), as: DashboardResponse.self)
    }

    func logs(lines: Int = 300) async throws -> LogResponse {
        try await execute(try request(path: "/api/logs?lines=\(lines)"), as: LogResponse.self)
    }

    func deals(lines: Int = 300) async throws -> DealsResponse {
        try await execute(try request(path: "/api/deals?lines=\(lines)"), as: DealsResponse.self)
    }

    func addTrackedProduct(ean: String) async throws -> APIAck {
        let body = try JSONSerialization.data(withJSONObject: ["ean": ean])
        return try await execute(try request(path: "/api/deals/products", method: "POST", body: body, contentType: "application/json"), as: APIAck.self)
    }

    func removeTrackedProduct(ean: String) async throws -> APIAck {
        let body = try JSONSerialization.data(withJSONObject: ["ean": ean])
        return try await execute(try request(path: "/api/deals/products/remove", method: "POST", body: body, contentType: "application/json"), as: APIAck.self)
    }

    func queueDownload(url: String) async throws -> APIAck {
        let body = try JSONSerialization.data(withJSONObject: ["url": url])
        return try await execute(try request(path: "/api/download", method: "POST", body: body, contentType: "application/json"), as: APIAck.self)
    }

    func uploadTorrent(data: Data, filename: String) async throws -> APIAck {
        let encoded = filename.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? filename
        let req = try request(
            path: "/api/torrent",
            method: "POST",
            body: data,
            contentType: "application/x-bittorrent",
            extraHeaders: ["X-Torrent-Filename": encoded]
        )
        return try await execute(req, as: APIAck.self)
    }
    func orbitStatus() async throws -> OrbitStatus {
        try await execute(try request(path: "/api/orbit/status"), as: OrbitStatus.self)
    }

    func revealOrbitCode(password: String) async throws -> OrbitPairCodeResponse {
        try await execute(try request(
            path: "/api/orbit/pair-code", method: "POST", body: Data("{}".utf8),
            contentType: "application/json",
            extraHeaders: ["X-Orbit-Action": "reveal-code", "X-Orbit-Pair-Password": password]
        ), as: OrbitPairCodeResponse.self)
    }

    func startOrbit(controlPassword: String) async throws -> OrbitStartResponse {
        guard let origin = URLComponents(url: baseURL, resolvingAgainstBaseURL: false),
              origin.scheme?.lowercased() == "https", let host = origin.host else {
            throw URLError(.badURL)
        }
        let hostname = host.contains(":") ? "[\(host)]" : host
        let port = origin.port.map { ":\($0)" } ?? ""
        // Nunca guardar la contraseña adicional: solo se usa en esta petición.
        return try await execute(try request(
            path: "/api/orbit/start", method: "POST", body: Data("{}".utf8),
            contentType: "application/json",
            extraHeaders: ["Origin": "https://\(hostname)\(port)",
                           "X-Orbit-Action": "start",
                           "X-Orbit-Control-Password": controlPassword]
        ), as: OrbitStartResponse.self)
    }

}
