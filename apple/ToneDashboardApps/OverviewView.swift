import SwiftUI

struct OverviewView: View {
    @EnvironmentObject private var session: DashboardSession

    private let columns = [GridItem(.adaptive(minimum: 155), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let error = session.lastError { ErrorBanner(message: error) }
                if !session.configured {
                    ContentUnavailableView("Configura el Dashboard", systemImage: "lock.shield", description: Text("Introduce URL, usuario y contraseña en Ajustes."))
                } else if let d = session.dashboard {
                    GroupBox("Servicios") {
                        LazyVGrid(columns: columns, spacing: 10) {
                            ForEach(d.services.keys.sorted(), id: \.self) { key in
                                let service = d.services[key]!
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(serviceName(key)).font(.subheadline.weight(.semibold))
                                        Text(service.state).font(.caption).foregroundStyle(DashboardPalette.muted)
                                    }
                                    Spacer()
                                    StatusPill(text: service.running ? "Activo" : "Parado", good: service.running)
                                }
                                .padding(10)
                                .background(DashboardPalette.panelSoft, in: RoundedRectangle(cornerRadius: 12))
                            }
                        }
                    }

                    Text("Mac mini").font(.title2.bold()).foregroundStyle(DashboardPalette.text)
                    LazyVGrid(columns: columns, spacing: 12) {
                        MetricCard(title: "CPU", value: percentString(d.system.cpuPercent), systemImage: "cpu")
                        MetricCard(title: "GPU", value: percentString(d.system.gpuPercent), subtitle: d.system.gpuPercent == nil ? d.system.powermetricsNote : "Residencia activa", systemImage: "display")
                        MetricCard(title: "RAM", value: percentString(d.system.ramPercent), subtitle: "\(byteString(d.system.ramUsed)) / \(byteString(d.system.ramTotal))", systemImage: "memorychip")
                        MetricCard(title: "Red ↓", value: speedString(d.system.netRxBps), subtitle: "↑ \(speedString(d.system.netTxBps))", systemImage: "network")
                        MetricCard(title: "Temperatura", value: d.system.temperatureC.map { String(format: "%.1f °C", $0) } ?? "—", subtitle: d.system.thermalState, systemImage: "thermometer.medium")
                    }
                    Text("Memoria libre por presión: \(percentString(d.system.memoryFreePercent)) · Swap: \(byteString(d.system.swapUsed))")
                        .font(.caption).foregroundStyle(DashboardPalette.muted)
                    Text("CPU: \(d.system.cpuTemperatureC.map { String(format: "%.1f °C", $0) } ?? "—") · GPU: \(d.system.gpuTemperatureC.map { String(format: "%.1f °C", $0) } ?? "—")")
                        .font(.caption).foregroundStyle(DashboardPalette.muted)
                    StorageCard(title: "Disco interno", used: d.internalDisk.used, total: d.internalDisk.total, subtitle: d.internalDisk.path)
                    StorageCard(title: "Disco Datos", used: d.disk.used, total: d.disk.total, subtitle: d.disk.path)

                    Text("Servidor Emby").font(.title2.bold()).foregroundStyle(DashboardPalette.text)
                    LazyVGrid(columns: columns, spacing: 12) {
                        MetricCard(title: "CPU", value: percentString(d.embySystem.cpuPercent), systemImage: "cpu")
                        MetricCard(title: "RAM", value: percentString(d.embySystem.ramPercent), subtitle: "\(byteString(d.embySystem.ramUsed)) / \(byteString(d.embySystem.ramTotal))", systemImage: "memorychip")
                        MetricCard(title: "Carga", value: d.embySystem.load1.map { String(format: "%.2f", $0) } ?? "—", subtitle: "5m \(d.embySystem.load5.map { String(format: "%.2f", $0) } ?? "—") · 15m \(d.embySystem.load15.map { String(format: "%.2f", $0) } ?? "—")", systemImage: "waveform.path.ecg")
                    }
                    if d.embyDisk.available == true {
                        StorageCard(title: "Almacenamiento Emby", used: d.embyDisk.used, total: d.embyDisk.total, subtitle: d.embyDisk.stale == true ? "Último dato válido" : d.embyDisk.path)
                    } else {
                        ErrorBanner(message: d.embyDisk.error ?? "No se pudo consultar el almacenamiento remoto")
                    }

                    Text("\(d.embySystem.stale == true ? "Último dato válido" : "Última lectura del sistema"): \(prettyDate(d.embySystem.updatedAt))")
                        .font(.caption).foregroundStyle(DashboardPalette.muted)
                    Text("Lectura de almacenamiento: \(prettyDate(d.embyDisk.updatedAt))")
                        .font(.caption).foregroundStyle(DashboardPalette.muted)
                    if let error = d.embySystem.error { ErrorBanner(message: error) }
                    if let error = d.embyDisk.lastError ?? d.embyDisk.error { ErrorBanner(message: error) }
                    Text("Últimas 24 horas").font(.title2.bold()).foregroundStyle(DashboardPalette.text)
                    LazyVGrid(columns: columns, spacing: 12) {
                        MetricCard(title: "Descargado", value: byteString(d.summary.history24h.downloadedBytes), systemImage: "arrow.down")
                        MetricCard(title: "Movido a Emby", value: byteString(d.summary.history24h.movedBytes), systemImage: "externaldrive.badge.checkmark")
                        MetricCard(title: "Eventos", value: "\(d.summary.history24h.count)", systemImage: "list.bullet")
                        MetricCard(title: "Correctos", value: "\(d.summary.history24h.success)", systemImage: "checkmark.circle")
                        MetricCard(title: "Errores", value: "\(d.summary.history24h.errors)", systemImage: "exclamationmark.triangle")
                    }
                } else if session.isLoading {
                    ProgressView("Cargando Dashboard…").frame(maxWidth: .infinity).padding(.top, 80)
                }
            }
            .padding()
        }
        .background(DashboardBackground())
        .foregroundStyle(DashboardPalette.text)
        .navigationTitle("ToneDashboardApps")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { Task { await session.refreshAll() } } label: { Image(systemName: "arrow.clockwise") }
            }
        }
        .refreshable { await session.refreshAll() }
    }

    private func serviceName(_ key: String) -> String {
        ["organizer":"Organizer", "telegram":"Telegram", "viewer":"Dashboard", "alerts":"Alertas"][key] ?? key
    }
}
