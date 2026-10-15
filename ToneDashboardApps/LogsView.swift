import SwiftUI

struct LogsView: View {
    @EnvironmentObject private var session: DashboardSession
    @State private var selected = "organizer_out"

    private let names: [(String, String, String)] = [
        ("organizer_out", "Organizer", "tray.full.fill"),
        ("organizer_err", "Errores", "exclamationmark.triangle.fill"),
        ("telegram_out", "Telegram", "paperplane.fill"),
        ("telegram_err", "Telegram · errores", "exclamationmark.bubble.fill"),
        ("ps5_out", "PS5", "gamecontroller.fill")
    ]

    private var selectedInfo: (String, String, String) {
        availableNames.first(where: { $0.0 == selected }) ?? availableNames[0]
    }

    private var availableNames: [(String, String, String)] {
        let known = Set(names.map { $0.0 })
        return names +
            session.logs.keys.sorted().filter { !known.contains($0) }.map { ($0, $0, "terminal.fill") }
    }

    private var selectedLog: String {
        session.logs[selected] ?? ""
    }

    var body: some View {
        VStack(spacing: 12) {
            if let error = session.lastError { ErrorBanner(message: error) }
            LogLineCountPicker()
            selector
                .frame(height: 40)

            logPanel
                .layoutPriority(1)
        }
        .padding(.horizontal, 14)
        .padding(.top, 8)
        .padding(.bottom, 10)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(DashboardBackground())
        .navigationTitle("Logs")
#if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
#endif
        .toolbar {
#if os(iOS)
            ToolbarItem(placement: .topBarTrailing) {
                refreshButton
            }
#else
            ToolbarItem(placement: .automatic) {
                refreshButton
            }
#endif
        }
    }

    private var refreshButton: some View {
        Button {
            Task { await session.refreshAll() }
        } label: {
            Image(systemName: "arrow.clockwise")
        }
        .accessibilityLabel("Actualizar logs")
    }

    private var selector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(availableNames, id: \.0) { item in
                    Button {
                        selected = item.0
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: item.2)
                                .font(.caption.weight(.semibold))

                            Text(item.1)
                                .font(.caption.weight(.semibold))
                                .lineLimit(1)
                        }
                        .foregroundStyle(
                            selected == item.0
                                ? DashboardPalette.backgroundDeep
                                : DashboardPalette.muted
                        )
                        .padding(.horizontal, 12)
                        .frame(height: 34)
                        .background(
                            selected == item.0
                                ? DashboardPalette.accent
                                : DashboardPalette.panelSoft,
                            in: Capsule()
                        )
                        .overlay {
                            Capsule()
                                .stroke(
                                    selected == item.0
                                        ? DashboardPalette.accent.opacity(0.35)
                                        : DashboardPalette.border,
                                    lineWidth: 1
                                )
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .frame(height: 40, alignment: .center)
            .padding(.horizontal, 1)
        }
        .frame(height: 40)
        .clipped()
    }

    private var logPanel: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: selectedInfo.2)
                    .foregroundStyle(DashboardPalette.accent)

                VStack(alignment: .leading, spacing: 2) {
                    Text(selectedInfo.1)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(DashboardPalette.text)

                    Text(
                        selectedLog.isEmpty
                            ? "Sin registros"
                            : "\(selectedLog.split(separator: "\n").count) líneas cargadas"
                    )
                    .font(.caption2)
                    .foregroundStyle(DashboardPalette.muted)
                }

                Spacer(minLength: 12)

                Circle()
                    .fill(selectedLog.isEmpty ? DashboardPalette.warning : DashboardPalette.ok)
                    .frame(width: 8, height: 8)
            }
            .frame(height: 52)
            .padding(.horizontal, 14)

            Divider()
                .overlay(DashboardPalette.border)

            logContent
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(DashboardPalette.backgroundDeep.opacity(0.94))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            DashboardPalette.panel,
            in: RoundedRectangle(cornerRadius: 18, style: .continuous)
        )
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(DashboardPalette.border, lineWidth: 1)
        }
    }

    @ViewBuilder
    private var logContent: some View {
#if os(iOS)
        ScrollView(.vertical, showsIndicators: true) {
            Text(selectedLog.isEmpty ? "(vacío)" : selectedLog)
                .font(.system(size: 11, weight: .regular, design: .monospaced))
                .foregroundStyle(DashboardPalette.ok)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .topLeading)
                .fixedSize(horizontal: false, vertical: true)
                .padding(14)
        }
#else
        ScrollView([.vertical, .horizontal], showsIndicators: true) {
            Text(selectedLog.isEmpty ? "(vacío)" : selectedLog)
                .font(.system(size: 11, weight: .regular, design: .monospaced))
                .foregroundStyle(DashboardPalette.ok)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .topLeading)
                .padding(14)
        }
#endif
    }
}


struct LogLineCountPicker: View {
    @EnvironmentObject private var session: DashboardSession
    var body: some View {
        Picker("Líneas de registro", selection: $session.logLines) {
            Text("100").tag(100)
            Text("300").tag(300)
            Text("1000").tag(1000)
        }
        .pickerStyle(.segmented)
        .onChange(of: session.logLines) { _, _ in Task { await session.refreshAll() } }
    }
}
