import Foundation

@main
struct APISecurityTests {
    static func main() {
        let base = URL(string: "https://dashboard.test")!
        let guardDelegate = DashboardRedirectGuard(baseURL: base)
        for target in ["https://dashboard.test/api", "https://DASHBOARD.test:443/api"] {
            precondition(DashboardRedirectGuard.trusted(URL(string: target)!, baseURL: base))
        }
        for target in ["http://dashboard.test/api", "https://evil.test/api",
                       "https://dashboard.test.evil.test/api", "https://dashboard.test:444/api",
                       "https://user:password@dashboard.test/api"] {
            precondition(!DashboardRedirectGuard.trusted(URL(string: target)!, baseURL: base))
        }
        let session = URLSession(configuration: .ephemeral)
        defer { session.invalidateAndCancel() }
        for method in ["GET", "POST"] {
            var original = URLRequest(url: base)
            original.httpMethod = method
            original.setValue("Basic test", forHTTPHeaderField: "Authorization")
            let task = session.dataTask(with: original)
            for target in ["https://dashboard.test/api", "https://evil.test/api", "http://dashboard.test/api"] {
                let redirect = URLRequest(url: URL(string: target)!)
                let response = HTTPURLResponse(url: base, statusCode: 302, httpVersion: "HTTP/1.1", headerFields: nil)!
                var called = false
                guardDelegate.urlSession(session, task: task, willPerformHTTPRedirection: response,
                                         newRequest: redirect) { accepted in
                    called = true
                    precondition((accepted != nil) == (method == "GET" && target == "https://dashboard.test/api"))
                }
                precondition(called)
            }
            task.cancel()
        }
        print("API security checks passed")
    }
}
