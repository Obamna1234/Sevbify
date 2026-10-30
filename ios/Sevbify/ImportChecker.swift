import SwiftUI
import UniformTypeIdentifiers

/// After a playlist file is imported: every song is looked up once (shared core: core/import_check.py). Found songs
/// get their cover, album and length; ones that can't be found as written come back with the closest song, and
/// Sevbify asks "Did you mean …?" so a typo doesn't stop them streaming or downloading.
@MainActor
final class ImportChecker: ObservableObject {
    static let shared = ImportChecker()
    struct Problem: Identifiable { let id: UUID; let written: String; var text: String; var on: Bool }
    @Published var checking = ""            // the playlist being checked
    @Published var done = 0
    @Published var total = 0
    @Published var reviewing = false
    @Published var problems: [Problem] = []
    var playlistId = ""

    static func asText(_ t: Track) -> String { t.artist.isEmpty ? t.title : "\(t.artist) - \(t.title)" }

    func start(_ pl: Playlist) {
        let lib = Library.shared
        guard lib.settings.online else { return }
        let todo = pl.tracks.filter { !$0.isLocal && lib.localFor($0) == nil }
        guard !todo.isEmpty else { return }
        checking = pl.name; done = 0; total = todo.count; playlistId = pl.id
        Task {
            var found: [Problem] = []
            for start in stride(from: 0, to: todo.count, by: 8) {
                let chunk = Array(todo[start..<min(start + 8, todo.count)])
                let json = (try? JSONSerialization.data(withJSONObject: chunk.map { $0.dict })).flatMap { String(data: $0, encoding: .utf8) } ?? "[]"
                guard let rows = try? await Bridge.list("check_import", [json]) else {
                    Player.shared.status = "Couldn't check the songs (offline?)"; checking = ""; return
                }
                for (t, r) in zip(chunk, rows) {
                    if r["status"] as? String == "ok", let d = r["track"] as? [String: Any] {
                        let f = Track(dict: d)
                        lib.update(pl.id) { p in
                            guard let i = p.tracks.firstIndex(where: { $0.uid == t.uid }) else { return }
                            if p.tracks[i].coverUrl.isEmpty { p.tracks[i].coverUrl = f.coverUrl }
                            if p.tracks[i].album.isEmpty { p.tracks[i].album = f.album }
                            if p.tracks[i].durationMs == 0 { p.tracks[i].durationMs = f.durationMs }
                        }
                    } else {
                        let s = r["suggestion"] as? String ?? ""
                        found.append(Problem(id: t.uid, written: Self.asText(t), text: s.isEmpty ? Self.asText(t) : s, on: !s.isEmpty))
                    }
                }
                done += chunk.count
            }
            checking = ""
            if found.isEmpty { Player.shared.status = "All \(todo.count) songs in “\(pl.name)” were found" }
            else { problems = found; reviewing = true }
        }
    }

    // --- More than 100 Spotify songs: Chosic's free exporter in Safari, then the file it downloads ---------------
    @Published var chosicAsk = false
    @Published var chosicPick = false
    @Published var chosicPicking = false
    var chosicId = ""
    var chosicLink = ""

    func offerChosic(_ id: String, _ link: String) { chosicId = id; chosicLink = link; chosicAsk = true }

    func openChosic() {
        UIPasteboard.general.string = chosicLink
        if let u = URL(string: "https://www.chosic.com/spotify-playlist-exporter/") { UIApplication.shared.open(u) }
        chosicPick = true
    }

    func addChosicFile(_ url: URL) {
        Task {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            let dir = FileManager.default.temporaryDirectory.appendingPathComponent("import", isDirectory: true)
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let copy = dir.appendingPathComponent(url.lastPathComponent)
            try? FileManager.default.removeItem(at: copy)
            defer { try? FileManager.default.removeItem(at: copy) }
            guard (try? FileManager.default.copyItem(at: url, to: copy)) != nil,
                  let o = try? await Bridge.object("import_file", [copy.path]) else {
                Player.shared.status = "Couldn't read that file"; return
            }
            let tracks = (o["items"] as? [[String: Any]] ?? []).compactMap { ($0["track"] as? [String: Any]).map(Track.init(dict:)) }
            let lib = Library.shared
            guard let pl = lib.playlist(chosicId), tracks.count > pl.tracks.count else {
                Player.shared.status = "That file has no more songs than the playlist"; return
            }
            lib.update(pl.id) { $0.tracks = tracks.map { $0.fresh() } }
            Player.shared.status = "“\(pl.name)” now has all \(tracks.count) songs"
            if let updated = lib.playlist(pl.id) { start(updated) }
        }
    }

    /// The ticked songs, renamed as typed ("Artist - Title").
    func apply() {
        let fixes = problems.filter { $0.on && !$0.text.isEmpty && $0.text != $0.written }
        Library.shared.update(playlistId) { p in
            for f in fixes {
                guard let i = p.tracks.firstIndex(where: { $0.uid == f.id }) else { continue }
                let parts = f.text.components(separatedBy: " - ")
                let artist = parts.count > 1 ? parts[0].trimmingCharacters(in: .whitespaces) : ""
                let title = parts.count > 1 ? parts.dropFirst().joined(separator: " - ").trimmingCharacters(in: .whitespaces) : f.text
                p.tracks[i] = Track(title: title, artist: artist)
            }
        }
        reviewing = false
        if !fixes.isEmpty { Player.shared.status = "Fixed \(fixes.count) song\(fixes.count == 1 ? "" : "s")" }
    }
}

/// "Check the spelling": the songs that couldn't be found, with the closest song filled in.
struct ImportReviewView: View {
    @ObservedObject var checker = ImportChecker.shared
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach($checker.problems) { $p in
                        VStack(alignment: .leading, spacing: 6) {
                            Toggle(isOn: $p.on) { Text(p.written).font(.caption).foregroundColor(C.dim) }.tint(C.green)
                            TextField("Artist - Title", text: $p.text).textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                        }
                    }
                } footer: {
                    Text("These couldn't be found as written, so they can't stream or download yet. Sevbify filled in the closest song it found. Or fix those lines in your file and import it again.")
                }
            }
            .navigationTitle("Check the spelling")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Keep as written") { checker.reviewing = false } }
                ToolbarItem(placement: .confirmationAction) { Button("Fix the ticked songs") { checker.apply() } }
            }
        }
    }
}

@MainActor
struct ImportReviewSheet: ViewModifier {
    @ObservedObject var checker = ImportChecker.shared
    func body(content: Content) -> some View {
        content.sheet(isPresented: $checker.reviewing) { ImportReviewView() }
            .alert("Spotify only shared the first 100 songs", isPresented: $checker.chosicAsk) {
                Button("Open Chosic") { checker.openChosic() }
                Button("Keep the first 100", role: .cancel) {}
            } message: {
                Text("Get all of them with Chosic's free Spotify Playlist Exporter. It opens in Safari with the link copied: paste it, press Export (CSV), then come back and pick the downloaded file.")
            }
            .alert("Add the file from Chosic", isPresented: $checker.chosicPick) {
                Button("Choose a file") { checker.chosicPicking = true }
                Button("Cancel", role: .cancel) {}
            } message: { Text("Pick the CSV Chosic downloaded (in Files → Downloads); it's added to the same playlist.") }
            .fileImporter(isPresented: $checker.chosicPicking, allowedContentTypes: [.commaSeparatedText, .plainText, .data]) { r in
                if case .success(let url) = r { checker.addChosicFile(url) }
            }
    }
}
