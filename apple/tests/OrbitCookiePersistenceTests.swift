import Foundation
import WebKit
import AppKit

@main struct CookieTest {
    @MainActor static func main() async {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        precondition(configuration.websiteDataStore.isPersistent, "Orbit cookies must survive app restarts")
        let host = "tone-orbit-test.invalid"
        let cookie = HTTPCookie(properties: [.domain:host, .path:"/", .name:"toneOrbitDevice",
            .value:"test-only-authorization", .secure:"TRUE", .expires:Date().addingTimeInterval(60),
            HTTPCookiePropertyKey("HttpOnly"):"TRUE"])!
        await configuration.websiteDataStore.httpCookieStore.setCookie(cookie)
        let recreated = WKWebViewConfiguration()
        recreated.websiteDataStore = .default()
        let cookies = await recreated.websiteDataStore.httpCookieStore.allCookies()
        precondition(cookies.contains { $0.domain == host && $0.name == "toneOrbitDevice" && $0.isSecure && $0.isHTTPOnly })
        await recreated.websiteDataStore.httpCookieStore.deleteCookie(cookie)
        let cleared = await configuration.websiteDataStore.httpCookieStore.allCookies()
        precondition(!cleared.contains { $0.domain == host && $0.name == "toneOrbitDevice" })
        print("WebKit: persistent store, secure HttpOnly cookie, view recreation and deletion passed")
    }
}
