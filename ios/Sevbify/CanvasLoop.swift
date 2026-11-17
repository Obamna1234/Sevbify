import AVFoundation
import CryptoKit
import SwiftUI

/// Canvas on iPhone, like the PC (core/canvas_loops.py) and Android: a silent 8-second loop from the song's official
/// music video. The shared core finds the video and where the loop starts; the clip is cut here with Apple's own
/// export tool (no re-encoding), so only those seconds are fetched. Streamed songs' clips live in a size-limited
/// cache; a downloaded song keeps its clip so it loops offline. Settings → Canvas turns it off.
@MainActor
final class CanvasLoop: ObservableObject {
    static let shared = CanvasLoop()
    @Published var current: URL?
    @AppStorage("sevbify.canvas.on") var on = true
    @AppStorage("sevbify.canvas.limit") var limitMb = 200
    @AppStorage("sevbify.canvas.keep") var keepDownloads = true
    let player = AVQueuePlayer()
    private var looper: AVPlayerLooper?
    private var busy = Set<String>()

    private init() { player.isMuted = true }

    nonisolated static func norm(_ s: String) -> String {
        s.lowercased().components(separatedBy: CharacterSet.alphanumerics.inverted).filter { !$0.isEmpty }.joined(separator: " ")
    }
    nonisolated static func key(_ artist: String, _ title: String) -> String {
        let d = Insecure.SHA1.hash(data: Data("\(norm(artist))|\(norm(title))".utf8))
        return String(d.map { String(format: "%02x", $0) }.joined().prefix(24))
    }
    private var cacheDir: URL {
        let u = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("canvas")
        try? FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
        return u
    }
    private var keptDir: URL {
        let u = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("canvas-kept")
        try? FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
        var v = URLResourceValues(); v.isExcludedFromBackup = true
        var copy = u; try? copy.setResourceValues(v)
        return u
    }

    func clip(for t: Track) -> URL? {
        let k = Self.key(t.artist, t.title)
        for dir in [keptDir, cacheDir] {
            let f = dir.appendingPathComponent("\(k).mp4")
            if let size = (try? FileManager.default.attributesOfItem(atPath: f.path)[.size]) as? Int, size > 10_000 {
                try? FileManager.default.setAttributes([.modificationDate: Date()], ofItemAtPath: f.path)
                return f
            }
        }
        return nil
    }

    func songChanged(_ t: Track?) {
        current = nil
        guard let t, !t.isItem, on else { stop(); return }
        if let f = clip(for: t) { show(f); return }
        stop()
        guard Library.shared.settings.online, !t.artist.isEmpty, t.artist != "Unknown Artist" else { return }
        let k = Self.key(t.artist, t.title)
        guard !busy.contains(k) else { return }
        busy.insert(k)
        Task {
            defer { busy.remove(k) }
            guard let src = try? await Bridge.object("canvas_source", [t.artist, t.title, t.durationMs]),
                  let urlString = src["url"] as? String, urlString.hasPrefix("https://"), let url = URL(string: urlString)
            else { return }
            let headers = src["headers"] as? [String: String] ?? [:]
            let start = src["start"] as? Double ?? 30
            let out = cacheDir.appendingPathComponent("\(k).mp4")
            if await Self.cut(url: url, headers: headers, start: start, to: out) {
                trim()
                if lib(isDownloaded: t) { keep(t) }
                if let now = Player.shared.current, Self.key(now.artist, now.title) == k { show(out) }
            }
        }
    }

    private func lib(isDownloaded t: Track) -> Bool { Library.shared.isDownloaded(t) }

    nonisolated static func cut(url: URL, headers: [String: String], start: Double, to out: URL) async -> Bool {
        let asset = AVURLAsset(url: url, options: ["AVURLAssetHTTPHeaderFieldsKey": headers])
        guard let export = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetPassthrough) else { return false }
        let part = out.deletingLastPathComponent().appendingPathComponent(out.lastPathComponent + ".part.mp4")
        try? FileManager.default.removeItem(at: part)
        export.outputURL = part
        export.outputFileType = .mp4
        export.timeRange = CMTimeRange(start: CMTime(seconds: start, preferredTimescale: 600),
                                       duration: CMTime(seconds: 8, preferredTimescale: 600))
        await export.export()
        guard export.status == .completed,
              let size = (try? FileManager.default.attributesOfItem(atPath: part.path)[.size]) as? Int,
              size > 10_000, size < 8_000_000 else {
            try? FileManager.default.removeItem(at: part)
            return false
        }
        try? FileManager.default.removeItem(at: out)
        return (try? FileManager.default.moveItem(at: part, to: out)) != nil
    }

    func keep(_ t: Track) {
        guard keepDownloads else { return }
        let k = Self.key(t.artist, t.title)
        let from = cacheDir.appendingPathComponent("\(k).mp4"), to = keptDir.appendingPathComponent("\(k).mp4")
        if FileManager.default.fileExists(atPath: from.path), !FileManager.default.fileExists(atPath: to.path) {
            try? FileManager.default.copyItem(at: from, to: to)
        }
    }

    func trim() {
        let fm = FileManager.default
        guard var files = try? fm.contentsOfDirectory(at: cacheDir, includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey])
            .filter({ $0.pathExtension == "mp4" }) else { return }
        files.sort { ((try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast)
                   < ((try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast) }
        var total = files.reduce(0) { $0 + ((try? $1.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0) }
        for f in files where total > limitMb * 1_048_576 {
            total -= (try? f.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
            try? fm.removeItem(at: f)
        }
    }

    var sizeMb: Double {
        let files = (try? FileManager.default.contentsOfDirectory(at: cacheDir, includingPropertiesForKeys: [.fileSizeKey])) ?? []
        return Double(files.reduce(0) { $0 + ((try? $1.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0) }) / 1_048_576
    }

    func clear() { try? FileManager.default.removeItem(at: cacheDir) }

    private func show(_ f: URL) {
        current = f
        looper = nil
        player.removeAllItems()
        looper = AVPlayerLooper(player: player, templateItem: AVPlayerItem(url: f))
        player.play()
    }

    func stop() { looper = nil; player.pause(); player.removeAllItems() }
}

/// The loop, filling a tall frame (the middle of the wide clip), like Spotify's Canvas.
struct CanvasLoopView: UIViewRepresentable {
    final class View: UIView {
        override class var layerClass: AnyClass { AVPlayerLayer.self }
        var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }
    }
    func makeUIView(context: Context) -> View {
        let v = View()
        v.playerLayer.player = CanvasLoop.shared.player
        v.playerLayer.videoGravity = .resizeAspectFill
        return v
    }
    func updateUIView(_ uiView: View, context: Context) {}
}

struct CanvasSettingsSection: View {
    @ObservedObject var canvas = CanvasLoop.shared
    var body: some View {
        Section("Canvas") {
            Toggle("Canvas from music videos", isOn: $canvas.on).tint(C.green)
            Toggle("Keep Canvas with downloaded songs", isOn: $canvas.keepDownloads).tint(C.green)
            Picker("Storage limit", selection: $canvas.limitMb) {
                ForEach([50, 100, 200, 500], id: \.self) { Text("\($0) MB") }
            }
            Button("Clear Canvas storage (\(Int(canvas.sizeMb)) MB)") { canvas.clear(); canvas.objectWillChange.send() }
            Text("When a song has an official music video on YouTube, a silent 8-second loop of it plays in Now playing (about 1 MB; only those seconds are fetched). Found with the same YouTube search Sevbify uses for songs.")
                .font(.caption).foregroundColor(C.dim)
        }
    }
}
