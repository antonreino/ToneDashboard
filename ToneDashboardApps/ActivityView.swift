import SwiftUI

struct ActivityView: View {
    @EnvironmentObject private var session: DashboardSession

    var body: some View {
        List {
            if let error = session.lastError { ErrorBanner(message: error) }
            if let stats = session.dashboard?.statistics {
                Section("Histórico completo") {
                    LabeledContent("Descargado", value: byteString(stats.downloadedBytes))
                    LabeledContent("Movido a Emby", value: byteString(stats.movedBytes))
                    LabeledContent("Total procesado", value: byteString(stats.totalBytes))
                    LabeledContent("Descargas completadas", value: "\(stats.downloadCount)")
                    LabeledContent("Archivos enviados", value: "\(stats.movedCount)")
                    LabeledContent("Desde", value: prettyDate(stats.firstEvent))
                }
                .listRowBackground(DashboardPalette.panel)
                Section("Estadísticas") {
                    ForEach(stats.periods) { period in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(period.label).font(.headline).foregroundStyle(DashboardPalette.text)
                            Text("Descargado: \(byteString(period.downloadedBytes)) · Emby: \(byteString(period.movedBytes))")
                                .font(.caption).foregroundStyle(DashboardPalette.muted)
                            Text("\(period.downloadCount) descargas · \(period.movedCount) archivos Emby")
                                .font(.caption).foregroundStyle(DashboardPalette.muted)
                        }
                    }
                }
                .listRowBackground(DashboardPalette.panel)
                Section("Por biblioteca") {
                    ForEach(stats.categories) { category in
                        LabeledContent(localizedCategory(category.category), value: "\(byteString(category.bytes)) · \(category.count) archivos")
                    }
                }
                .listRowBackground(DashboardPalette.panel)
            }
            Section("Historial del sistema") {
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
                        Text(localizedActivityKind(item.kind)).font(.caption).foregroundStyle(DashboardPalette.muted)
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
