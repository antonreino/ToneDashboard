import Foundation
@main struct ContainerTests {
    @MainActor static func main() async {
        let base = URL(string:"https://dashboard.test")!
        for value in ["https://dashboard.test/","https://dashboard.test/orbit-bridge/zero/","https://DASHBOARD.test/api/deals"] {
            precondition(DashboardOrigin.trusted(URL(string:value)!,baseURL:base))
        }
        for value in ["http://dashboard.test/","https://dashboard.test.evil/","https://other.test/","https://dashboard.test:444/","https://user:secret@dashboard.test/","file:///etc/passwd","javascript:alert(1)"] {
            precondition(!DashboardOrigin.trusted(URL(string:value)!,baseURL:base))
        }
        precondition(DashboardOrigin.request(baseURL:base).url?.path == "/")
        precondition(DashboardOrigin.request(baseURL:base).value(forHTTPHeaderField:"Authorization") == nil)
        precondition(DashboardOrigin.acceptsChallenge(host:"dashboard.test",port:443,scheme:"https",method:NSURLAuthenticationMethodHTTPBasic,failures:0,baseURL:base))
        for (host,port,scheme,method,failures) in [("evil.test",443,"https",NSURLAuthenticationMethodHTTPBasic,0),("dashboard.test",80,"http",NSURLAuthenticationMethodHTTPBasic,0),("dashboard.test",443,"https",NSURLAuthenticationMethodHTTPBasic,1),("dashboard.test",443,"https",NSURLAuthenticationMethodServerTrust,0)] {
            precondition(!DashboardOrigin.acceptsChallenge(host:host,port:port,scheme:scheme,method:method,failures:failures,baseURL:base))
        }
        let suite="ToneDashboard-migration-tests-"+UUID().uuidString
        let defaults=UserDefaults(suiteName:suite)!
        defer { defaults.removePersistentDomain(forName:suite) }
        defaults.set("https://dashboard.test",forKey:"baseURL"); defaults.set("existing-user",forKey:"username")
        let session=DashboardSession(defaults:defaults,passwordLoader:{ account in precondition(account=="existing-user");return "keychain-secret" })
        precondition(session.configured && session.username=="existing-user" && session.password=="keychain-secret")
        precondition(defaults.string(forKey:"password")==nil)
        precondition(session.usesLegacyWebStore)
        session.username = "other-user"
        precondition(!session.usesLegacyWebStore)
        session.username = "existing-user"
        precondition(session.usesLegacyWebStore)
        print("Container checks passed: HTTPS, origin isolation, auth challenges, root UI and existing settings migration")
    }
}
