import Foundation

struct DashboardResponse: Codable {
    var services: [String: ServiceState]
    var summary: Summary
    var statistics: Statistics
    var downloads: [DownloadItem]
    var history: [HistoryItem]
    var disk: DiskInfo
    var internalDisk: DiskInfo
    var embyDisk: RemoteDisk
    var embySystem: EmbySystem
    var system: MacSystem

    enum CodingKeys: String, CodingKey {
        case services, summary, statistics, downloads, history, disk, system
        case internalDisk = "internal_disk"
        case embyDisk = "emby_disk"
        case embySystem = "emby_system"
    }
}

struct ServiceState: Codable, Hashable {
    var running: Bool
    var state: String
}

struct Summary: Codable {
    var downloads: [String: Int]
    var history24h: History24h
    enum CodingKeys: String, CodingKey {
        case downloads
        case history24h = "history_24h"
    }
}

struct History24h: Codable {
    var count: Int
    var success: Int
    var errors: Int
    var bytes: Int64
    var downloadedBytes: Int64
    var movedBytes: Int64
    enum CodingKeys: String, CodingKey {
        case count, success, errors, bytes
        case downloadedBytes = "downloaded_bytes"
        case movedBytes = "moved_bytes"
    }
}

struct Statistics: Codable {
    var downloadedBytes: Int64
    var movedBytes: Int64
    var totalBytes: Int64
    var downloadCount: Int
    var movedCount: Int
    var periods: [PeriodStat]
    var categories: [CategoryStat]
    var firstEvent: String?
    var lastEvent: String?
    enum CodingKeys: String, CodingKey {
        case periods, categories
        case downloadedBytes = "downloaded_bytes"
        case movedBytes = "moved_bytes"
        case totalBytes = "total_bytes"
        case downloadCount = "download_count"
        case movedCount = "moved_count"
        case firstEvent = "first_event"
        case lastEvent = "last_event"
    }
}

struct PeriodStat: Codable, Identifiable {
    var id: String { label }
    var label: String
    var downloadedBytes: Int64
    var movedBytes: Int64
    var downloadCount: Int
    var movedCount: Int
    enum CodingKeys: String, CodingKey {
        case label
        case downloadedBytes = "downloaded_bytes"
        case movedBytes = "moved_bytes"
        case downloadCount = "download_count"
        case movedCount = "moved_count"
    }
}

struct CategoryStat: Codable, Identifiable {
    var id: String { category }
    var category: String
    var bytes: Int64
    var count: Int
}

struct DownloadItem: Codable, Identifiable {
    var id: Int
    var createdAt: String?
    var updatedAt: String?
    var name: String?
    var target: String?
    var sizeBytes: Int64?
    var resumeSupported: Int?
    var status: String?
    var queuedAt: Double?
    var startedAt: Double?
    var finishedAt: Double?
    var attempt: Int?
    var error: String?
    var downloadedBytes: Int64?
    var speedBps: Double?
    var progressPercent: Double?
    var etaSeconds: Int?

    enum CodingKeys: String, CodingKey {
        case id, name, target, status, attempt, error
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case sizeBytes = "size_bytes"
        case resumeSupported = "resume_supported"
        case queuedAt = "queued_at"
        case startedAt = "started_at"
        case finishedAt = "finished_at"
        case downloadedBytes = "downloaded_bytes"
        case speedBps = "speed_bps"
        case progressPercent = "progress_percent"
        case etaSeconds = "eta_seconds"
    }
}

struct HistoryItem: Codable, Identifiable {
    var id: Int
    var createdAt: String?
    var kind: String?
    var status: String?
    var title: String?
    var category: String?
    var sourcePath: String?
    var destination: String?
    var details: String?
    var sizeBytes: Int64?
    var jobId: Int?

    enum CodingKeys: String, CodingKey {
        case id, kind, status, title, category, destination, details
        case createdAt = "created_at"
        case sourcePath = "source_path"
        case sizeBytes = "size_bytes"
        case jobId = "job_id"
    }
}

struct DiskInfo: Codable {
    var path: String
    var exists: Bool
    var total: Int64
    var used: Int64
    var free: Int64
}

struct RemoteDisk: Codable {
    var available: Bool?
    var path: String?
    var total: Int64?
    var used: Int64?
    var free: Int64?
    var usedPercent: Double?
    var updatedAt: String?
    var stale: Bool?
    var error: String?
    var lastError: String?

    enum CodingKeys: String, CodingKey {
        case available, path, total, used, free, stale, error
        case usedPercent = "used_percent"
        case updatedAt = "updated_at"
        case lastError = "last_error"
    }
}

struct EmbySystem: Codable {
    var available: Bool?
    var cpuPercent: Double?
    var ramTotal: Int64?
    var ramUsed: Int64?
    var ramAvailable: Int64?
    var ramPercent: Double?
    var load1: Double?
    var load5: Double?
    var load15: Double?
    var updatedAt: String?
    var stale: Bool?
    var error: String?

    enum CodingKeys: String, CodingKey {
        case available, stale, error
        case cpuPercent = "cpu_percent"
        case ramTotal = "ram_total"
        case ramUsed = "ram_used"
        case ramAvailable = "ram_available"
        case ramPercent = "ram_percent"
        case load1 = "load_1"
        case load5 = "load_5"
        case load15 = "load_15"
        case updatedAt = "updated_at"
    }
}

struct MacSystem: Codable {
    var cpuPercent: Double?
    var gpuPercent: Double?
    var temperatureC: Double?
    var cpuTemperatureC: Double?
    var gpuTemperatureC: Double?
    var thermalState: String?
    var ramTotal: Int64?
    var ramUsed: Int64?
    var ramPercent: Double?
    var memoryFreePercent: Double?
    var swapUsed: Int64?
    var netRxBps: Double?
    var netTxBps: Double?
    var powermetricsNote: String?

    enum CodingKeys: String, CodingKey {
        case cpuPercent = "cpu_percent"
        case gpuPercent = "gpu_percent"
        case temperatureC = "temperature_c"
        case cpuTemperatureC = "cpu_temperature_c"
        case gpuTemperatureC = "gpu_temperature_c"
        case thermalState = "thermal_state"
        case ramTotal = "ram_total"
        case ramUsed = "ram_used"
        case ramPercent = "ram_percent"
        case memoryFreePercent = "memory_free_percent"
        case swapUsed = "swap_used"
        case netRxBps = "net_rx_bps"
        case netTxBps = "net_tx_bps"
        case powermetricsNote = "powermetrics_note"
    }
}

struct LogResponse: Codable {
    var logs: [String: String]
}

struct DealsResponse: Codable {
    var available: Bool
    var error: String?
    var activeOffers: [Offer]
    var history: [DealHistory]
    var events: [DealEvent]
    var log: String?
    enum CodingKeys: String, CodingKey {
        case available, error, history, events, log
        case activeOffers = "active_offers"
    }
}

struct Offer: Codable, Identifiable {
    var id: String { "\(source ?? "")|\(url ?? "")|\(title ?? "")" }
    var family: String?
    var kind: String?
    var price: Int?
    var availability: String?
    var title: String?
    var source: String?
    var seller: String?
    var shipping: Int?
    var url: String?
    var seenIso: String?
    enum CodingKeys: String, CodingKey {
        case family, kind, price, availability, title, source, seller, shipping, url
        case seenIso = "seen_iso"
    }
}

struct DealHistory: Codable, Identifiable {
    var id: String { "\(createdIso ?? "")|\(body)" }
    var body: String
    var createdIso: String?
    enum CodingKeys: String, CodingKey {
        case body
        case createdIso = "created_iso"
    }
}

struct DealEvent: Codable, Identifiable {
    var id: String { "\(createdIso ?? "")|\(name)|\(detail)" }
    var name: String
    var level: String
    var detail: String
    var createdIso: String?
    enum CodingKeys: String, CodingKey {
        case name, level, detail
        case createdIso = "created_iso"
    }
}

struct APIAck: Codable {
    var ok: Bool?
    var name: String?
    var requestId: Int?
    var error: String?
    enum CodingKeys: String, CodingKey {
        case ok, name, error
        case requestId = "request_id"
    }
}


// API de control de Orbit Zero en ToneDashboard. El código de vinculación
// nunca se devuelve ni se almacena en la aplicación.
struct OrbitStatus: Decodable {
    let running: Bool
    let can_start: Bool
    let start_configured: Bool
    let pair_code_available: Bool
}

struct OrbitStartResponse: Decodable {
    let running: Bool?
    let message: String?
    let error: String?
}
