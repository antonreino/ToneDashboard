import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var session: DashboardSession

    var body: some View {
        ZStack {
            DashboardBackground()
            TabView {
                NavigationStack { OverviewView() }
                    .tabItem { Label("Inicio", systemImage: "house.fill") }
                NavigationStack { DownloadsView() }
                    .tabItem { Label("Descargas", systemImage: "arrow.down.circle.fill") }
                NavigationStack { ActivityView() }
                    .tabItem { Label("Actividad", systemImage: "clock.arrow.circlepath") }
                NavigationStack { DealsView() }
                    .tabItem { Label("Ofertas", systemImage: "tag.fill") }
                LogsView()
                    .tabItem { Label("Logs", systemImage: "terminal.fill") }
                SettingsView()
                    .tabItem { Label("Ajustes", systemImage: "gearshape.fill") }
            }
            .tint(DashboardPalette.accent)
        }
        .preferredColorScheme(.dark)
        .overlay(alignment: .top) {
            if let toast = session.toast {
                Text(toast)
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(DashboardPalette.text)
                    .padding(.horizontal, 14).padding(.vertical, 9)
                    .background(DashboardPalette.panel, in: Capsule())
                    .overlay { Capsule().stroke(DashboardPalette.border, lineWidth: 1) }
                    .padding(.top, 8)
                    .onAppear {
                        Task {
                            try? await Task.sleep(for: .seconds(3))
                            await MainActor.run { session.toast = nil }
                        }
                    }
            }
        }
    }
}
