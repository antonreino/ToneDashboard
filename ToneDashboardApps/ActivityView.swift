import SwiftUI

struct ActivityView: View {
    @EnvironmentObject private var session: DashboardSession

    var body: some View {
        List {
            if let stats = session.dashboard?.statistics {
                Section("Estadísticas") {
                    ForEach(stats.periods) { period in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(period.label).font(.headline).foregroundStyle(DashboardPalette.text)
                            Text("Descargado: \(byteString(period.downloadedBytes)) · Emby: \(byteString(period.movedBytes))")
                                .font(.caption).foregroundStyle(DashboardPalette.muted)
                        }
                    }
                }
                .listRowBackground(DashboardPalette.panel)
            }
            Section("Historial de descargas") {
                if (session.dashboard?.history ?? []).isEmpty {
                    Text("No hay actividad registrada.").foregroundStyle(DashboardPalette.muted)
                }
                ForEach(session.dashboard?.history ?? []) { item in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Text(item.title ?? localizedActivityKind(item.kind)).font(.headline).foregroundStyle(DashboardPalette.text)
                            Spacer()
                            StatusPill(text: localizedStatus(item.status), good: isGoodStatus(item.status))
                        }
                        if let details = item.details { Text(details).font(.subheadline).foregroundStyle(DashboardPalette.text) }
                        HStack {
                            if let category = item.category { Text(localizedCategory(category)) }
                            Spacer()
                            Text(prettyDate(item.createdAt))
                        }
                        .font(.caption)
                        .foregroundStyle(DashboardPalette.muted)
                    }
                    .padding(.vertical, 4)
                }
            }
            .listRowBackground(DashboardPalette.panel)
        }
        .dashboardListStyle()
        .navigationTitle("Actividad")
        .refreshable { await session.refreshAll() }
    }
}
