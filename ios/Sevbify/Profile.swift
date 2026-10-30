import SwiftUI
import UniformTypeIdentifiers

/// Your Sevbify profile: one small file (".sevbify") with your playlists, followed shows, where you stopped, recently
/// played, recent searches and settings. The same file opens in Sevbify on Android, Windows, macOS and Linux
/// (format: core/profile.py). It's only where you save it (Files, iCloud Drive, a password manager...). On an iPhone,
/// deleting an app deletes its folder too, so export your profile before deleting Sevbify.
enum Profile {
    static let fileName = "Sevbify profile.sevbify"
    static let type = UTType(filenameExtension: "sevbify") ?? .data

    @MainActor static func build() -> [String: Any] {
        let lib = Library.shared, s = lib.settings
        return [
            "from": "iphone",
            "folders": lib.libraryFolders,
            "playlists": lib.playlists.map { p -> [String: Any] in
                ["name": p.name, "folder": p.folder, "pinned": p.pinned, "origin": p.origin, "cover_url": p.coverUrl,
                 "created": Int(p.created), "tracks": p.tracks.map { $0.dict }]
            },
            "resume": lib.resume.mapValues { Int($0 * 1000) },
            "recent": lib.recent.prefix(50).map { $0.dict },
            "searches": lib.searches,
            "settings": ["online": s.online, "stream_full": s.streamFull, "explicit_ok": s.explicitOk,
                         "autoplay": s.autoplay, "song_quality": s.songQuality,
                         "show_playlist_origin": s.showPlaylistOrigin, "shuffle": s.shuffle, "repeat": s.repeatMode],
        ]
    }

    @MainActor static func data() async throws -> Data {
        let b64 = try await Bridge.call("profile_pack", [Bridge.json(build())]) as? String ?? ""
        guard let d = Data(base64Encoded: b64) else { throw Bridge.Failure(message: "Couldn't make the profile") }
        return d
    }

    /// Adds what's in a profile (never replaces your playlists; the same playlist twice is skipped).
    @MainActor static func importFile(_ url: URL) async throws -> String {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        let raw = try Data(contentsOf: url)
        let d = try await Bridge.object("profile_unpack", [raw.base64EncodedString()])
        let lib = Library.shared
        for f in d["folders"] as? [String] ?? [] where !lib.libraryFolders.contains(f) { lib.libraryFolders.append(f) }
        let pls = d["playlists"] as? [[String: Any]] ?? []
        var added = 0
        for p in pls {
            let name = p["name"] as? String ?? "Playlist"
            let tracks = (p["tracks"] as? [[String: Any]] ?? []).map(Track.init(dict:))
            let keys = tracks.map { $0.matchKey }
            if lib.playlists.contains(where: { $0.name.lowercased() == name.lowercased() && $0.tracks.map { $0.matchKey } == keys }) { continue }
            let pl = lib.newPlaylist(uniqueName(name, lib.playlists.map { $0.name }), tracks: tracks,
                                     origin: p["origin"] as? String ?? "")
            lib.update(pl.id) {
                $0.folder = p["folder"] as? String ?? ""; $0.pinned = p["pinned"] as? Bool ?? false
                $0.coverUrl = p["cover_url"] as? String ?? ""
            }
            added += 1
        }
        for (k, v) in d["resume"] as? [String: Any] ?? [:] where lib.resume[k] == nil {
            if let ms = (v as? NSNumber)?.doubleValue { lib.resume[k] = ms / 1000 }
        }
        var merged = lib.searches
        for q in d["searches"] as? [String] ?? [] where !merged.contains(where: { $0.lowercased() == q.lowercased() }) { merged.append(q) }
        lib.searches = Array(merged.prefix(30))
        if let m = d["settings"] as? [String: Any] {
            var s = lib.settings
            if let v = m["online"] as? Bool { s.online = v }
            if let v = m["stream_full"] as? Bool { s.streamFull = v }
            if let v = m["explicit_ok"] as? Bool { s.explicitOk = v }
            if let v = m["autoplay"] as? Bool { s.autoplay = v }
            if let v = m["song_quality"] as? String, ["best", "small"].contains(v) { s.songQuality = v }
            if let v = m["show_playlist_origin"] as? Bool { s.showPlaylistOrigin = v }
            lib.settings = s
        }
        lib.save()
        return added == pls.count ? "Profile imported: \(added) playlists added"
                                  : "Profile imported: \(added) playlists added (the rest were already here)"
    }

    static func uniqueName(_ wanted: String, _ existing: [String]) -> String {
        let taken = Set(existing.map { $0.lowercased() })
        if !taken.contains(wanted.lowercased()) { return wanted }
        var n = 1, name = "\(wanted) (imported)"
        while taken.contains(name.lowercased()) { n += 1; name = "\(wanted) (imported \(n))" }
        return name
    }
}

/// The file handed to the "Export" picker.
struct ProfileDocument: FileDocument {
    static var readableContentTypes: [UTType] { [Profile.type, .data] }
    var data: Data
    init(data: Data) { self.data = data }
    init(configuration: ReadConfiguration) throws { data = configuration.file.regularFileContents ?? Data() }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}

/// Settings ▸ Your Sevbify profile.
struct ProfileSection: View {
    @EnvironmentObject var player: Player
    @State private var exportDoc: ProfileDocument? = nil
    @State private var exporting = false
    @State private var importing = false

    var body: some View {
        Section {
            Button("Export profile…") {
                Task {
                    do { exportDoc = ProfileDocument(data: try await Profile.data()); exporting = true }
                    catch { player.status = "Couldn't make the profile: \(error.localizedDescription)" }
                }
            }
            Button("Import profile…") { importing = true }
        } header: { Text("Your Sevbify profile") } footer: {
            Text("One small file with your playlists, podcasts, where you stopped, recently played, recent searches and settings. It opens in Sevbify on any device (iPhone, Android, Windows, Mac, Linux) and stays where you save it: Sevbify never uploads it. Deleting an iPhone app deletes its files, so export your profile first (to Files, iCloud Drive or your password manager).")
        }
        .fileExporter(isPresented: $exporting, document: exportDoc, contentType: Profile.type,
                      defaultFilename: Profile.fileName) { result in
            if case .failure(let e) = result { player.status = "Couldn't save: \(e.localizedDescription)" }
            else { player.status = "Profile saved" }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [Profile.type, .data]) { result in
            guard case .success(let url) = result else { return }
            Task {
                do { player.status = try await Profile.importFile(url) }
                catch { player.status = "Couldn't import: \(error.localizedDescription)" }
            }
        }
    }
}
