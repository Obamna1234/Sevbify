import Network
import SwiftUI

/// Smart downloads, like Spotify's and the PC's and Android's: a streamed song in your playlists that you played at
/// least 3 times in the last 30 days is downloaded for you, at most 20 a day, only on Wi-Fi (never on mobile data).
/// Off unless you turn it on in Settings. Worked out on this iPhone.
@MainActor
final class SmartDownloads: ObservableObject {
    static let shared = SmartDownloads()
    @AppStorage("sevbify.smart.on") var on = false
    @AppStorage("sevbify.smart.day") private var day = ""
    private let monitor = NWPathMonitor()
    private var unmetered = false
    private var last = Date.distantPast

    private init() {
        monitor.pathUpdateHandler = { path in
            let ok = path.status == .satisfied && !path.isExpensive && !path.isConstrained
            Task { @MainActor in SmartDownloads.shared.unmetered = ok }
        }
        monitor.start(queue: DispatchQueue(label: "sevbify.smart"))
    }

    func check(force: Bool = false) {
        let lib = Library.shared
        guard on, lib.settings.online, unmetered, force || Date().timeIntervalSince(last) > 600 else { return }
        last = Date()
        let f = DateFormatter(); f.dateFormat = "yyyyMMdd"
        let today = f.string(from: Date())
        let parts = day.split(separator: ":")
        let done = parts.count == 2 && parts[0] == today ? Int(parts[1]) ?? 0 : 0
        let room = 20 - done
        guard room > 0 else { return }
        let since = Int(Date().timeIntervalSince1970) - 30 * 86400
        var counts: [String: Int] = [:]
        for r in Listens.all() where r.count >= 3 {
            guard let a = r[0] as? String, let t = r[1] as? String, let at = (r[2] as? NSNumber)?.intValue, at >= since else { continue }
            counts[Track.matchKey(a, t), default: 0] += 1
        }
        var seen = Set<String>()
        let picks = lib.playlists.flatMap { $0.tracks }
            .filter { t in !t.isItem && seen.insert(t.matchKey).inserted && (counts[t.matchKey] ?? 0) >= 3
                      && !lib.isDownloaded(t) && Downloads.shared.state(of: t) == nil }
            .sorted { (counts[$0.matchKey] ?? 0) > (counts[$1.matchKey] ?? 0) }
            .prefix(room)
        guard !picks.isEmpty else { return }
        Downloads.shared.download(Array(picks))
        day = "\(today):\(done + picks.count)"
        Task { _ = try? await Bridge.call("log_event", ["download", "smart downloads: \(picks.count) song(s) you keep playing"]) }
    }
}

struct SmartDownloadsSection: View {
    @ObservedObject var smart = SmartDownloads.shared
    var body: some View {
        Section {
            Toggle("Smart downloads", isOn: Binding(get: { smart.on }, set: { smart.on = $0; if $0 { smart.check(force: true) } }))
                .tint(C.green)
        } footer: {
            Text("Songs in your playlists that you keep playing (3 times in a month) are downloaded for you on Wi-Fi, so they play offline too. At most 20 a day.")
        }
    }
}
