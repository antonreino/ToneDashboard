import SwiftUI

enum DashboardPalette {
    static let background = Color(red: 7/255, green: 17/255, blue: 31/255)
    static let backgroundDeep = Color(red: 5/255, green: 11/255, blue: 22/255)
    static let panel = Color(red: 13/255, green: 22/255, blue: 40/255).opacity(0.92)
    static let panelSoft = Color.white.opacity(0.045)
    static let border = Color.white.opacity(0.08)
    static let text = Color(red: 238/255, green: 244/255, blue: 1)
    static let muted = Color(red: 157/255, green: 176/255, blue: 206/255)
    static let accent = Color(red: 110/255, green: 168/255, blue: 1)
    static let accent2 = Color(red: 143/255, green: 124/255, blue: 1)
    static let ok = Color(red: 48/255, green: 209/255, blue: 88/255)
    static let warning = Color(red: 1, green: 179/255, blue: 64/255)
    static let bad = Color(red: 1, green: 93/255, blue: 115/255)
    static let cyan = Color(red: 73/255, green: 214/255, blue: 1)
}

struct DashboardBackground: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [DashboardPalette.backgroundDeep, DashboardPalette.background, DashboardPalette.backgroundDeep],
                startPoint: .top,
                endPoint: .bottom
            )
            RadialGradient(
                colors: [DashboardPalette.accent.opacity(0.18), .clear],
                center: .topLeading,
                startRadius: 0,
                endRadius: 520
            )
            RadialGradient(
                colors: [DashboardPalette.accent2.opacity(0.16), .clear],
                center: .topTrailing,
                startRadius: 0,
                endRadius: 460
            )
        }
        .ignoresSafeArea()
    }
}

struct DashboardPanel<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding()
            .background(DashboardPalette.panel, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(DashboardPalette.border, lineWidth: 1)
            }
    }
}

struct MetricCard: View {
    let title: String
    let value: String
    var subtitle: String? = nil
    var systemImage: String = "gauge.with.dots.needle.50percent"

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(title, systemImage: systemImage)
                .font(.caption.weight(.semibold))
                .foregroundStyle(DashboardPalette.muted)
            Text(value)
                .font(.title2.bold())
                .monospacedDigit()
                .foregroundStyle(DashboardPalette.text)
            if let subtitle {
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(DashboardPalette.muted)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(DashboardPalette.panel, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(DashboardPalette.border, lineWidth: 1)
        }
    }
}

struct StorageCard: View {
    let title: String
    let used: Int64?
    let total: Int64?
    var subtitle: String? = nil

    var ratio: Double {
        guard let used, let total, total > 0 else { return 0 }
        return min(1, max(0, Double(used) / Double(total)))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.headline).foregroundStyle(DashboardPalette.text)
            ProgressView(value: ratio).tint(DashboardPalette.accent)
            HStack {
                Text("\(byteString(used)) usados")
                Spacer()
                Text("\(byteString(total)) total")
            }
            .font(.caption)
            .foregroundStyle(DashboardPalette.muted)
            if let subtitle { Text(subtitle).font(.caption2).foregroundStyle(DashboardPalette.muted) }
        }
        .padding()
        .background(DashboardPalette.panel, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(DashboardPalette.border, lineWidth: 1)
        }
    }
}

struct StatusPill: View {
    let text: String
    let good: Bool
    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 9).padding(.vertical, 5)
            .background((good ? DashboardPalette.ok : DashboardPalette.warning).opacity(0.15), in: Capsule())
            .foregroundStyle(good ? DashboardPalette.ok : DashboardPalette.warning)
    }
}

struct ErrorBanner: View {
    let message: String
    var body: some View {
        Label(message, systemImage: "exclamationmark.triangle.fill")
            .font(.callout)
            .foregroundStyle(DashboardPalette.bad)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .background(DashboardPalette.bad.opacity(0.10), in: RoundedRectangle(cornerRadius: 14))
            .overlay {
                RoundedRectangle(cornerRadius: 14).stroke(DashboardPalette.bad.opacity(0.22), lineWidth: 1)
            }
    }
}

extension View {
    func dashboardListStyle() -> some View {
        self
            .scrollContentBackground(.hidden)
            .background(DashboardBackground())
            .foregroundStyle(DashboardPalette.text)
            .tint(DashboardPalette.accent)
    }
}
