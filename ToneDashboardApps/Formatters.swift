import Foundation

func byteString(_ value: Int64?) -> String {
    guard let value else { return "—" }
    let formatter = ByteCountFormatter()
    formatter.countStyle = .file
    formatter.allowedUnits = [.useKB, .useMB, .useGB, .useTB]
    return formatter.string(fromByteCount: value)
}

func speedString(_ value: Double?) -> String {
    guard let value else { return "—" }
    return byteString(Int64(value)) + "/s"
}

func percentString(_ value: Double?) -> String {
    guard let value else { return "—" }
    return String(format: "%.1f%%", value)
}

func euroString(cents: Int?) -> String {
    guard let cents else { return "—" }
    let formatter = NumberFormatter()
    formatter.locale = Locale(identifier: "es_ES")
    formatter.numberStyle = .currency
    formatter.currencyCode = "EUR"
    return formatter.string(from: NSNumber(value: Double(cents) / 100.0)) ?? "\(cents / 100) €"
}

private let spanishDateFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "es_ES")
    formatter.timeZone = .current
    formatter.dateFormat = "d 'de' MMMM 'de' yyyy, HH:mm"
    return formatter
}()

private let isoFormatters: [ISO8601DateFormatter] = {
    let normal = ISO8601DateFormatter()
    normal.formatOptions = [.withInternetDateTime]
    let fractional = ISO8601DateFormatter()
    fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return [fractional, normal]
}()

func prettyDate(_ iso: String?) -> String {
    guard let iso, !iso.isEmpty else { return "—" }
    for parser in isoFormatters {
        if let date = parser.date(from: iso) {
            return spanishDateFormatter.string(from: date)
        }
    }

    let fallbackFormats = [
        "yyyy-MM-dd HH:mm:ss.SSSSSS",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
        "yyyy-MM-dd'T'HH:mm:ss"
    ]
    for format in fallbackFormats {
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.dateFormat = format
        if let date = parser.date(from: iso) {
            return spanishDateFormatter.string(from: date)
        }
    }
    return iso
}

func localizedStatus(_ status: String?) -> String {
    guard let raw = status?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty else { return "—" }
    switch raw.lowercased() {
    case "queued", "queue", "pending": return "En cola"
    case "active", "running", "downloading", "processing": return "En curso"
    case "completed", "complete", "success", "succeeded", "ok": return "Completado"
    case "failed", "failure", "error": return "Error"
    case "cancelled", "canceled": return "Cancelado"
    case "paused": return "Pausado"
    case "retrying", "retry": return "Reintentando"
    case "skipped": return "Omitido"
    case "moved": return "Movido a Emby"
    default:
        return raw.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

func isGoodStatus(_ status: String?) -> Bool {
    guard let value = status?.lowercased() else { return false }
    return ["completed", "complete", "success", "succeeded", "ok", "moved"].contains(value)
}

func localizedActivityKind(_ kind: String?) -> String {
    guard let raw = kind, !raw.isEmpty else { return "Actividad" }
    switch raw.lowercased() {
    case "download", "direct_download": return "Descarga"
    case "torrent": return "Torrent"
    case "move", "moved": return "Movimiento a Emby"
    case "organizer", "organize": return "Organización"
    case "error": return "Error"
    default: return raw.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

func localizedCategory(_ category: String) -> String {
    switch category.lowercased() {
    case "movie", "movies": return "Películas"
    case "series", "tv", "shows": return "Series"
    case "anime": return "Anime"
    case "games", "game": return "Juegos"
    case "download", "downloads": return "Descargas"
    default: return category.replacingOccurrences(of: "_", with: " ").capitalized
    }
}
