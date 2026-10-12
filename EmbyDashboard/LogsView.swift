import SwiftUI

struct LogsView: View {
    @EnvironmentObject private var session: DashboardSession
    @State private var selected = "organizer_out"

    private let names: [(String, String)] = [
        ("organizer_out", "Organizer"),
        ("organizer_err", "Organizer · errores"),
        ("telegram_out", "Telegram"),
        ("telegram_err", "Telegram · errores"),
        ("ps5_out", "PS5")
    ]

    var body: some View {
        VStack(spacing: 0) {
            Picker("Log", selection: $selected) {
                ForEach(names, id: \.0) { Text($0.1).tag($0.0) }
            }
            .pickerStyle(.segmented)
            .tint(DashboardPalette.accent)
            .padding()

            ScrollView([.vertical, .horizontal]) {
                Text(session.logs[selected] ?? "(vacío)")
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                    .padding()
            }
            .background(DashboardPalette.backgroundDeep.opacity(0.96))
            .foregroundStyle(DashboardPalette.ok)
        }
        .background(DashboardBackground())
        .navigationTitle("Logs")
        .toolbar {
            Button { Task { await session.refreshAll() } } label: { Image(systemName: "arrow.clockwise") }
        }
    }
}
