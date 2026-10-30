import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var lib: Library
    @State private var ytdlp = ""
    @State private var python = ""
    @State private var updating = false
    @State private var updateMessage = ""
    @State private var appUpdate = ""
    private let sources = ["Bandcamp + YouTube", "Bandcamp only", "YouTube only"]

    var body: some View {
        Form {
            Section {
                Toggle("Online features", isOn: Binding(get: { lib.settings.online }, set: { v in
                    lib.settings.online = v
                    Task { _ = try? await Bridge.call("set_online", [v]) }
                }))
                Toggle("Allow explicit songs", isOn: $lib.settings.explicitOk)
            } footer: {
                Text("No account, no ads, no tracking, nothing sold. Online, Sevbify only contacts what each feature needs: Deezer (search, radio, genres), Wikipedia (artist info), DuckDuckGo (only a finished search whose results look wrong, for “Did you mean”), Apple (podcast directory), Bandcamp and YouTube (full songs, downloads), Spotify, Apple Music or Deezer only when you import a link, song.link when you share, and GitHub for updates.")
            }
            Section("Playback") {
                Toggle("Autoplay similar songs when your music ends", isOn: $lib.settings.autoplay)
            }
            Section {
                Picker("Download and stream from", selection: Binding(get: { lib.settings.source }, set: { v in
                    lib.settings.source = v
                    Task { _ = try? await Bridge.call("set_source", [v]) }
                })) { ForEach(sources, id: \.self) { Text($0) } }
                Picker("Download quality", selection: $lib.settings.songQuality) {
                    Text("Best (original audio)").tag("best")
                    Text("Data saver (smaller)").tag("small")
                }
            } header: { Text("Downloads") } footer: {
                Text("Songs are saved in Files ▸ On My iPhone ▸ Sevbify ▸ Music. Downloads keep going while music plays; if you close Sevbify, unfinished ones wait for next time.")
            }
            ProfileSection()
            Section("Your Library") {
                Toggle("Show where playlists came from", isOn: $lib.settings.showPlaylistOrigin)
                Text("A coloured border around playlist pictures: grey = made in Sevbify, green = Spotify link, white = Apple Music link, purple = Deezer link, orange = Jamendo link, blue = imported from a file.")
                    .font(.caption).foregroundColor(C.dim)
            }
            Section {
                LabeledContent("yt-dlp (finds full songs)", value: ytdlp)
                Button(updating ? "Checking…" : "Update yt-dlp") {
                    updating = true
                    Task {
                        if let o = try? await Bridge.object("update_ytdlp") { updateMessage = o["message"] as? String ?? "" }
                        else { updateMessage = "Couldn't check for an update" }
                        updating = false
                        await refresh()
                    }
                }.disabled(updating)
                if !updateMessage.isEmpty { Text(updateMessage).font(.caption).foregroundColor(C.dim) }
            } header: { Text("Updates") } footer: {
                Text("YouTube changes often; a newer yt-dlp (the official release, checksum-checked) fixes most \"couldn't find the full song\" problems. It's used after Sevbify restarts.")
            }
            Section {
                Button("Check for Sevbify updates") {
                    Task { appUpdate = await AppUpdates.shared.check(manual: true) }
                }
                Button("Add Sevbify to SideStore") { AppUpdates.shared.openStore("sidestore") }
                Button("Add Sevbify to AltStore") { AppUpdates.shared.openStore("altstore") }
                if !appUpdate.isEmpty { Text(appUpdate).font(.caption).foregroundColor(C.dim) }
            } header: { Text("Sevbify updates") } footer: {
                Text("Once Sevbify's source is added, SideStore or AltStore offer each new version like an App Store update. Sevbify also tells you once when a new version is out.")
            }
            Section {
                Button("Language") {
                    if let u = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(u) }
                }
            } footer: {
                Text("Sevbify follows your iPhone's language. To use another one just for Sevbify: Settings → Sevbify → Language. Search works in every language either way.")
            }
            Section("About") {
                LabeledContent("Sevbify", value: Bundle.main.object(forInfoDictionaryKey: "SevbifyVersion") as? String ?? "")
                LabeledContent("Python", value: python)
                Text("Built with AI help (Anthropic's Claude). Not affiliated with Spotify, YouTube, Bandcamp, Apple or Deezer.")
                    .font(.caption).foregroundColor(C.dim)
            }
        }
        .scrollContentBackground(.hidden).background(C.bg.ignoresSafeArea())
        .navigationTitle("Settings")
        .task { await refresh() }
    }

    private func refresh() async {
        if let o = try? await Bridge.object("ytdlp_info") { ytdlp = o["version"] as? String ?? "" }
        if let o = try? await Bridge.object("python_info") { python = "\(o["python"] ?? "") (\(o["platform"] ?? ""))" }
        if python.isEmpty, let e = Bridge.startError { python = e }
    }
}

/// For the automatic build: start with a screen open (-SEVTab search -SEVQuery "daft punk") and, with
/// -SEVSmoke, check Python and the online features and write the result to Documents/smoke.json.
enum Smoke {
    static var args: [String] { ProcessInfo.processInfo.arguments }
    static func value(_ name: String) -> String? {
        guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
        return args[i + 1]
    }
    static var initialQuery: String { value("-SEVQuery") ?? "" }

    @MainActor static func runIfAsked() {
        if let tab = value("-SEVTab") {
            Library.shared.settings.noticeAccepted = true
            Nav.current?.tab = tab == "search" ? .search : (tab == "library" ? .library : .home)
        }
        if value("-SEVPlay") != nil { Task { await playFirstSearchResult() } }
        guard args.contains("-SEVSmoke") else { return }
        Task.detached {
            var out: [String: Any] = [:]
            out["python_start"] = Bridge.startError ?? "ok"
            out["python_info"] = (try? Bridge.callSync("python_info")) ?? "failed"
            do {
                let found = try Bridge.callSync("search", ["daft punk", 5]) as? [[String: Any]] ?? []
                out["search"] = found.map { "\($0["artist"] ?? "") - \($0["title"] ?? "")" }
            } catch { out["search"] = "failed: \(error.localizedDescription)" }
            do {
                let g = try Bridge.callSync("genres") as? [[String: Any]] ?? []
                out["genres"] = g.count
            } catch { out["genres"] = "failed: \(error.localizedDescription)" }
            do {
                let r = try Bridge.callSync("radio", ["Daft Punk", "One More Time", 10]) as? [[String: Any]] ?? []
                out["radio"] = r.count
            } catch { out["radio"] = "failed: \(error.localizedDescription)" }
            do {
                let o = try Bridge.callSync("resolve", ["Perturbator", "Future Club", 0]) as? [String: Any] ?? [:]
                out["full_song"] = "\(o["source"] ?? "") \((o["url"] as? String)?.prefix(40) ?? "")"
            } catch { out["full_song"] = "failed: \(error.localizedDescription)" }
            let local = await MainActor.run { Library.shared.localSongs.count }
            out["local_songs"] = local
            let data = (try? JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys])) ?? Data()
            try? data.write(to: Library.documents.appendingPathComponent("smoke.json"))
        }
    }

    @MainActor static func playFirstSearchResult() async {
        let q = initialQuery.isEmpty ? "daft punk" : initialQuery
        guard let songs = try? await Bridge.tracks("search", [q, 10]), let first = songs.first else { return }
        Player.shared.play(first, in: songs, source: "Search: \(q)")
        if value("-SEVPlay") == "open" { Nav.current?.nowPlaying = true }
    }
}
