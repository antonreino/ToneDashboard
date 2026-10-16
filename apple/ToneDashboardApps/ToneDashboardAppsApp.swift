import SwiftUI
@main struct ToneDashboardApp: App {
    @StateObject private var session = DashboardSession()
    var body: some Scene {
        WindowGroup("Tone Dashboard") { ContentView().environmentObject(session) }
    }
}
