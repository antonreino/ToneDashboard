import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var session: DashboardSession
    @State private var showPassword = false

    var body: some View {
        Form {
            Section("Servidor") {
                TextField("URL", text: $session.baseURLString)
                TextField("Usuario", text: $session.username)
                if showPassword {
                    TextField("Contraseña", text: $session.password)
                } else {
                    SecureField("Contraseña", text: $session.password)
                }
                Toggle("Mostrar contraseña", isOn: $showPassword)
                    .tint(DashboardPalette.accent)
                Button("Guardar y comprobar", systemImage: "checkmark.shield.fill") {
                    Task { await session.saveSettings() }
                }
                .buttonStyle(.borderedProminent)
                .tint(DashboardPalette.accent)
            }
            .listRowBackground(DashboardPalette.panel)

            Section("Estado") {
                LabeledContent("Última actualización", value: session.lastUpdated.map { spanishTime($0) } ?? "—")
                if let error = session.lastError { Text(error).foregroundStyle(DashboardPalette.bad) }
            }
            .listRowBackground(DashboardPalette.panel)

            Section("Seguridad") {
                Text("La contraseña se almacena en Keychain. No se guarda en UserDefaults ni está incluida en el proyecto.")
                    .font(.caption).foregroundStyle(DashboardPalette.muted)
            }
            .listRowBackground(DashboardPalette.panel)
        }
        .dashboardListStyle()
        .navigationTitle("Ajustes")
    }

    private func spanishTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "es_ES")
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: date)
    }
}
