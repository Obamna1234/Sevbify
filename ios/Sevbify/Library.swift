import Foundation
import SwiftUI

struct Settings: Codable {
    var online = true
    var streamFull = true
    var source = "Bandcamp + YouTube"
    var autoplay = true
    var explicitOk = true
    var songQuality = "best"            // core/quality.py: "best" (original) | "small" (data saver)
    var shuffle = false
    var repeatMode = "off"              // "off" | "all" | "one"
    var showPlaylistOrigin = false
    var lastfmKey = ""
    var jamendoId = ""
    var noticeAccepted = false
    var lastAppCheck: Double = 0          // last daily check for a new Sevbify
    var updateAsked = ""                  // newest version already offered (asked once per version)

    init() {}
    enum CodingKeys: String, CodingKey {
        case online, streamFull, source, autoplay, explicitOk, songQuality, shuffle, repeatMode, showPlaylistOrigin,
             lastfmKey, jamendoId, noticeAccepted, lastAppCheck, updateAsked
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func b(_ k: CodingKeys, _ d: Bool) -> Bool { (try? c.decode(Bool.self, forKey: k)) ?? d }
        func s(_ k: CodingKeys, _ d: String) -> String { (try? c.decode(String.self, forKey: k)) ?? d }
        online = b(.online, true); streamFull = b(.streamFull, true); source = s(.source, "Bandcamp + YouTube")
        autoplay = b(.autoplay, true); explicitOk = b(.explicitOk, true); songQuality = s(.songQuality, "best")
        shuffle = b(.shuffle, false); repeatMode = s(.repeatMode, "off"); showPlaylistOrigin = b(.showPlaylistOrigin, false)
        lastfmKey = s(.lastfmKey, ""); jamendoId = s(.jamendoId, ""); noticeAccepted = b(.noticeAccepted, false)
        lastAppCheck = (try? c.decode(Double.self, forKey: .lastAppCheck)) ?? 0; updateAsked = s(.updateAsked, "")
    }
}

/// A folder you added from the Files app (read in place; Sevbify only ever looks inside folders you add).
struct LinkedFolder: Codable, Identifiable, Hashable {
    var id = UUID().uuidString
    var name: String
    var bookmark: Data
}

private struct SaveFile: Codable {
    var playlists: [Playlist] = []
    var settings = Settings()
    var folders: [LinkedFolder] = []
    var recent: [Track] = []
    var resume: [String: Double] = [:]
    var searches: [String] = []
    var libraryFolders: [String] = []

    init(playlists: [Playlist], settings: Settings, folders: [LinkedFolder], recent: [Track], resume: [String: Double],
         searches: [String], libraryFolders: [String]) {
        self.playlists = playlists; self.settings = settings; self.folders = folders; self.recent = recent
        self.resume = resume; self.searches = searches; self.libraryFolders = libraryFolders
    }
    // Every part is optional, so saves from older versions always load.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        playlists = (try? c.decode([Playlist].self, forKey: .playlists)) ?? []
        settings = (try? c.decode(Settings.self, forKey: .settings)) ?? Settings()
        folders = (try? c.decode([LinkedFolder].self, forKey: .folders)) ?? []
        recent = (try? c.decode([Track].self, forKey: .recent)) ?? []
        resume = (try? c.decode([String: Double].self, forKey: .resume)) ?? [:]
        searches = (try? c.decode([String].self, forKey: .searches)) ?? []
        libraryFolders = (try? c.decode([String].self, forKey: .libraryFolders)) ?? []
    }
}

/// Everything Sevbify keeps on this iPhone: playlists, settings, your songs. Saved as one JSON file in the app's
/// own private folder (nothing leaves the phone).
@MainActor
final class Library: ObservableObject {
    static let shared = Library()

    @Published var playlists: [Playlist] = []
    @Published var settings = Settings() { didSet { save() } }
    @Published var folders: [LinkedFolder] = []
    @Published var localSongs: [Track] = []
    @Published var recent: [Track] = []
    @Published var searches: [String] = []          // Search ▸ Recent searches (newest first)
    var libraryFolders: [String] = []                 // playlist folders from a profile made on another device
    @Published var scanning = false
    var resume: [String: Double] = [:]

    private var byKey: [String: Track] = [:]
    private var loading = false

    nonisolated static var documents: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }
    nonisolated static var support: URL {
        let u = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Sevbify", isDirectory: true)
        try? FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
        return u
    }
    nonisolated static var musicFolder: URL {
        let u = documents.appendingPathComponent("Music", isDirectory: true)
        try? FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
        return u
    }
    private var file: URL { Library.support.appendingPathComponent("library.json") }

    init() { load() }

    func load() {
        loading = true; defer { loading = false }
        guard let data = try? Data(contentsOf: file) else { return }
        do {
            let s = try JSONDecoder().decode(SaveFile.self, from: data)
            playlists = s.playlists; settings = s.settings; folders = s.folders; recent = s.recent; resume = s.resume
            searches = s.searches; libraryFolders = s.libraryFolders
        } catch {
            // Keep a damaged file instead of overwriting it, so nothing is lost.
            try? FileManager.default.copyItem(at: file, to: file.appendingPathExtension("damaged-\(Int(Date().timeIntervalSince1970))"))
        }
    }

    private var saveTask: Task<Void, Never>?
    func save() {
        if loading { return }
        let snapshot = SaveFile(playlists: playlists, settings: settings, folders: folders,
                                recent: Array(recent.prefix(50)), resume: resume, searches: Array(searches.prefix(30)),
                                libraryFolders: libraryFolders)
        let target = file
        saveTask?.cancel()
        saveTask = Task.detached(priority: .utility) {
            try? await Task.sleep(nanoseconds: 300_000_000)
            if Task.isCancelled { return }
            if let data = try? JSONEncoder().encode(snapshot) { try? data.write(to: target, options: .atomic) }
        }
    }

    func changed() { objectWillChange.send(); save() }

    // --- playlists ------------------------------------------------------------------------------------------
    @discardableResult
    func newPlaylist(_ name: String? = nil, tracks: [Track] = [], origin: String = "") -> Playlist {
        var n = playlists.count + 1
        let wanted = name?.trimmingCharacters(in: .whitespaces) ?? ""
        var base = wanted.isEmpty ? "My Playlist #\(n)" : wanted
        while playlists.contains(where: { $0.name.lowercased() == base.lowercased() }) {
            n += 1
            base = wanted.isEmpty ? "My Playlist #\(n)" : "\(wanted) \(n)"
        }
        var pl = Playlist(name: base, tracks: tracks.map { $0.fresh() })
        pl.origin = origin
        playlists.insert(pl, at: 0)
        save()
        return pl
    }

    func index(of id: String) -> Int? { playlists.firstIndex { $0.id == id } }
    func playlist(_ id: String) -> Playlist? { playlists.first { $0.id == id } }

    func update(_ id: String, _ change: (inout Playlist) -> Void) {
        guard let i = index(of: id) else { return }
        change(&playlists[i])
        save()
    }

    func add(_ tracks: [Track], to id: String) { update(id) { $0.tracks.append(contentsOf: tracks.map { $0.fresh() }) } }
    func delete(_ id: String) { playlists.removeAll { $0.id == id }; save() }

    /// A search you stayed on for a moment, like Spotify's Recent searches (only on this iPhone).
    func rememberSearch(_ q: String) {
        let text = q.trimmingCharacters(in: .whitespaces)
        guard text.count >= 2 else { return }
        searches.removeAll { $0.lowercased() == text.lowercased() }
        searches.insert(text, at: 0)
        if searches.count > 30 { searches.removeLast(searches.count - 30) }
        save()
    }

    func addRecent(_ t: Track) {
        recent.removeAll { $0.matchKey == t.matchKey }
        recent.insert(t, at: 0)
        if recent.count > 50 { recent.removeLast(recent.count - 50) }
        save()
    }

    // --- your own songs -------------------------------------------------------------------------------------
    /// The file on this iPhone for a song, if you have it.
    func localFor(_ t: Track) -> Track? { t.isLocal ? t : byKey[t.matchKey] }
    func isDownloaded(_ t: Track) -> Bool { localFor(t) != nil }

    func url(for t: Track) -> URL? {
        let p = t.localPath
        if p.hasPrefix("docs:") { return Library.documents.appendingPathComponent(String(p.dropFirst(5))) }
        if p.hasPrefix("link:") {
            let rest = p.dropFirst(5)
            guard let slash = rest.firstIndex(of: "/") else { return nil }
            let id = String(rest[..<slash]), rel = String(rest[rest.index(after: slash)...])
            guard let f = folders.first(where: { $0.id == id }), let base = resolve(f) else { return nil }
            return base.appendingPathComponent(rel)
        }
        return nil
    }

    /// Folders you added, opened once and kept open while the app runs (closed again when you remove one).
    private var opened: [String: URL] = [:]

    func resolve(_ f: LinkedFolder) -> URL? {
        if let u = opened[f.id] { return u }
        var stale = false
        guard let u = try? URL(resolvingBookmarkData: f.bookmark, bookmarkDataIsStale: &stale) else { return nil }
        guard u.startAccessingSecurityScopedResource() else { return nil }
        opened[f.id] = u
        return u
    }

    func addFolder(_ url: URL) {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let bm = try? url.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil) else { return }
        if folders.contains(where: { $0.name == url.lastPathComponent && $0.bookmark == bm }) { return }
        folders.append(LinkedFolder(name: url.lastPathComponent, bookmark: bm))
        save()
        Task { await scan() }
    }

    func removeFolder(_ f: LinkedFolder) {
        if let u = opened.removeValue(forKey: f.id) { u.stopAccessingSecurityScopedResource() }   // Sevbify can't read it any more
        folders.removeAll { $0.id == f.id }; save(); Task { await scan() }
    }

    /// Reads Sevbify's own folder (downloads and anything you put there with the Files app or Finder) and the
    /// folders you added. Tags are read by the shared Python code (mutagen).
    func scan() async {
        if scanning { return }
        scanning = true
        var found: [Track] = []
        let roots: [(String, URL)] = [("docs:", Library.documents)] + folders.compactMap { f in
            resolve(f).map { ("link:\(f.id)/", $0) }
        }
        for (prefix, root) in roots {
            let art = Library.support.appendingPathComponent("art", isDirectory: true).path
            let items = (try? await Bridge.list("scan_folder", [root.path, art])) ?? []
            for d in items {
                guard let path = d["path"] as? String else { continue }
                var t = Track(title: d["title"] as? String ?? "", artist: d["artist"] as? String ?? "")
                t.album = d["album"] as? String ?? ""
                t.durationMs = (d["duration_ms"] as? NSNumber)?.intValue ?? 0
                let rel = path.hasPrefix(root.path) ? String(path.dropFirst(root.path.count)).trimmingCharacters(in: CharacterSet(charactersIn: "/")) : path
                t.localPath = prefix + rel
                if let a = d["art"] as? String, !a.isEmpty { t.localArt = URL(fileURLWithPath: a).absoluteString }
                found.append(t)
            }
        }
        found.sort { ($0.artist.lowercased(), $0.title.lowercased()) < ($1.artist.lowercased(), $1.title.lowercased()) }
        localSongs = found
        var map: [String: Track] = [:]
        for t in found where map[t.matchKey] == nil { map[t.matchKey] = t }
        byKey = map
        scanning = false
    }
}
