import SwiftUI
import UniformTypeIdentifiers

struct DownloadsView: View {
    @EnvironmentObject private var session: DashboardSession
    @State private var directURL = ""
    @State private var importingTorrent = false

    private var torrentType: UTType { UTType(filenameExtension: "torrent") ?? .data }

    var body: some View {
        List {
            Section("Añadir descarga directa") {
                TextField("Introducir URL", text: $directURL)
                    .textFieldStyle(.roundedBorder)
                Button("Añadir a la cola", systemImage: "plus.circle.fill") {
                    let value = directURL
                    Task {
                        if await session.queueDownload(value) { directURL = "" }
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(DashboardPalette.accent)
                .disabled(directURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .listRowBackground(DashboardPalette.panel)

            Section("Torrent") {
                Button("Seleccionar .torrent", systemImage: "doc.badge.plus") { importingTorrent = true }
                    .foregroundStyle(DashboardPalette.accent)
                Text("Se guardará en la misma carpeta que los torrents recibidos por Telegram.")
                    .font(.caption).foregroundStyle(DashboardPalette.muted)
            }
            .listRowBackground(DashboardPalette.panel)

            if let downloads = session.dashboard?.downloads {
                Section("Descargas recientes") {
                    if downloads.isEmpty { Text("No hay descargas registradas.").foregroundStyle(DashboardPalette.muted) }
                    ForEach(downloads) { item in DownloadRow(item: item) }
                }
                .listRowBackground(DashboardPalette.panel)
            }
        }
        .dashboardListStyle()
        .navigationTitle("Descargas")
        .fileImporter(isPresented: $importingTorrent, allowedContentTypes: [torrentType], allowsMultipleSelection: false) { result in
            guard case .success(let urls) = result, let url = urls.first else { return }
            Task { _ = await session.uploadTorrent(url: url) }
        }
        .refreshable { await session.refreshAll() }
    }
}

struct DownloadRow: View {
    let item: DownloadItem
    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text(item.name ?? "Descarga #\(item.id)").font(.headline).foregroundStyle(DashboardPalette.text)
                Spacer()
                StatusPill(
                    text: localizedStatus(item.status),
                    good: isGoodStatus(item.status)
                )
            }
            if let p = item.progressPercent {
                ProgressView(value: p, total: 100).tint(DashboardPalette.accent)
                HStack {
                    Text(String(format: "%.1f%%", p))
                    Spacer()
                    if item.speedBps != nil { Text(speedString(item.speedBps)) }
                }.font(.caption).foregroundStyle(DashboardPalette.muted)
            }
            if let error = item.error, !error.isEmpty { Text(error).font(.caption).foregroundStyle(DashboardPalette.bad) }
        }
        .padding(.vertical, 4)
    }
}
