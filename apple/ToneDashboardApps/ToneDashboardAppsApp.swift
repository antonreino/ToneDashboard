import SwiftUI

@main
struct ToneDashboardAppsApp: App {
    @StateObject private var session = DashboardSession()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(session)
                .task { await session.bootstrap() }
        }
        #if os(macOS)
        .defaultSize(width: 1180, height: 780)
        #endif
    }
}
