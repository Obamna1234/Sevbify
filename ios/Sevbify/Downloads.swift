import Foundation
import UIKit

/// Downloads songs into Sevbify's own folder (On My iPhone ▸ Sevbify ▸ Music ▸ <Artist>, visible in the Files
/// app). One at a time, with the shared core's engine: Bandcamp first, then YouTube, original audio kept.
/// The iPhone keeps going while music plays; if Sevbify is closed, unfinished downloads wait for next time.
@MainActor
final class Downloads: ObservableObject {
    static let shared = Downloads()

    struct Job: Identifiable, Equatable {
        let id = UUID()
        let track: Track
        var state = "Waiting"                // Waiting | Downloading | Done | Failed: ...
    }

    @Published private(set) var jobs: [Job] = []
    private var running = false

    var active: Int { jobs.filter { $0.state == "Waiting" || $0.state == "Downloading" }.count }
    func state(of t: Track) -> String? {
        jobs.last(where: { $0.track.matchKey == t.matchKey })?.state
    }

    func download(_ tracks: [Track]) {
        let lib = Library.shared
        guard lib.settings.online else { Player.shared.status = "Downloading needs the internet"; return }
        var added = 0
        for t in tracks where !lib.isDownloaded(t) && !t.isItem {
            if jobs.contains(where: { $0.track.matchKey == t.matchKey && ($0.state == "Waiting" || $0.state == "Downloading") }) { continue }
            jobs.append(Job(track: t)); added += 1
        }
        if added > 0 { Player.shared.status = added == 1 ? "Downloading \(tracks[0].title)" : "Downloading \(added) songs" }
        runNext()
    }

    func clearFinished() { jobs.removeAll { $0.state == "Done" || $0.state.hasPrefix("Failed") } }

    private func runNext() {
        guard !running, let i = jobs.firstIndex(where: { $0.state == "Waiting" }) else { return }
        running = true
        jobs[i].state = "Downloading"
        let id = jobs[i].id, t = jobs[i].track
        let quality = Library.shared.settings.songQuality
        // A little extra time if the app is sent to the background mid-download.
        var bg: UIBackgroundTaskIdentifier = .invalid
        bg = UIApplication.shared.beginBackgroundTask(withName: "download") { UIApplication.shared.endBackgroundTask(bg) }
        Task {
            var result = "Done"
            do {
                let o = try await Bridge.object("download_song", [t.artist, t.title, t.durationMs,
                                                                   Library.musicFolder.path, quality])
                if o["path"] is String { await Library.shared.scan() }      // shows up in Your Songs
            } catch {
                result = "Failed: \(error.localizedDescription)"
            }
            if let j = jobs.firstIndex(where: { $0.id == id }) { jobs[j].state = result }
            UIApplication.shared.endBackgroundTask(bg)
            running = false
            runNext()
        }
    }
}
