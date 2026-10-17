import Foundation

// Shared web content never receives the password through JavaScript or a bridge.
enum DashboardOrigin {
    static func valid(_ url: URL) -> Bool {
        url.scheme?.lowercased() == "https" && url.host != nil && url.user == nil && url.password == nil
    }
    static func trusted(_ url: URL, baseURL: URL) -> Bool {
        valid(url) && valid(baseURL) && url.host?.lowercased() == baseURL.host?.lowercased() && (url.port ?? 443) == (baseURL.port ?? 443)
    }
    static func diagnosticBlob(_ url: URL, sourceURL: URL, baseURL: URL) -> Bool {
        guard trusted(sourceURL,baseURL:baseURL), url.scheme == "blob",
              let inner = URL(string:String(url.absoluteString.dropFirst(5))) else { return false }
        return trusted(inner,baseURL:baseURL)
    }
    static func permitsFrame(_ url: URL, sourceURL: URL, baseURL: URL) -> Bool {
        valid(url) && (trusted(sourceURL,baseURL:baseURL) || trusted(url,baseURL:sourceURL))
    }
    static func request(baseURL: URL) -> URLRequest {
        var request = URLRequest(url: URL(string: "/", relativeTo: baseURL)!.absoluteURL)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        return request
    }
    static func acceptsChallenge(host: String, port: Int, scheme: String?, method: String, failures: Int, baseURL: URL) -> Bool {
        valid(baseURL) && scheme?.lowercased() == "https" && host.lowercased() == baseURL.host?.lowercased() && port == (baseURL.port ?? 443) && method == NSURLAuthenticationMethodHTTPBasic && failures == 0
    }
}
