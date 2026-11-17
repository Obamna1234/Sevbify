import SwiftUI

/// Podcasts on iPhone, like the PC's and Android's: browse the top shows, search Apple's podcast directory (and the
/// show's own YouTube channel), open a show, play its episodes (they continue where you stopped), follow shows, save
/// episodes to Your Episodes and mark them as played. All through the shared core; the feeds are read directly.
struct ShowRef: Hashable {
    let json: String
    init(_ d: [String: Any]) { json = Bridge.json(d) }
    var dict: [String: Any] {
        (try? JSONSerialization.jsonObject(with: Data(json.utf8))) as? [String: Any] ?? [:]
    }
    var key: String { dict["key"] as? String ?? "" }
    var title: String { dict["title"] as? String ?? "" }
    var author: String { dict["author"] as? String ?? "" }
    var image: String { dict["image_url"] as? String ?? dict["cover_url"] as? String ?? "" }
}

@MainActor
final class Shows: ObservableObject {
    static let shared = Shows()
    @Published private(set) var followed: [ShowRef] = []
    @Published private(set) var saved: [Track] = []           // Your Episodes, newest first
    @Published private(set) var played: Set<String> = []
    private let d = UserDefaults.standard

    private init() {
        followed = (d.array(forKey: "sevbify.shows") as? [String] ?? []).compactMap { s in
            ((try? JSONSerialization.jsonObject(with: Data(s.utf8))) as? [String: Any]).map(ShowRef.init)
        }
        if let data = d.data(forKey: "sevbify.episodes"), let t = try? JSONDecoder().decode([Track].self, from: data) { saved = t }
        played = Set(d.stringArray(forKey: "sevbify.played") ?? [])
    }

    func isFollowed(_ s: ShowRef) -> Bool { followed.contains { $0.key == s.key } }
    func toggleFollow(_ s: ShowRef) {
        if isFollowed(s) { followed.removeAll { $0.key == s.key } } else { followed.insert(s, at: 0) }
        d.set(followed.map(\.json), forKey: "sevbify.shows")
    }
    func isSaved(_ t: Track) -> Bool { saved.contains { $0.itemKey == t.itemKey } }
    func toggleSaved(_ t: Track) {
        if isSaved(t) { saved.removeAll { $0.itemKey == t.itemKey } } else { saved.insert(t, at: 0) }
        if saved.count > 500 { saved = Array(saved.prefix(500)) }
        if let data = try? JSONEncoder().encode(saved) { d.set(data, forKey: "sevbify.episodes") }
    }
    func isPlayed(_ t: Track) -> Bool { played.contains(t.itemKey) }
    func setPlayed(_ t: Track, _ on: Bool) {
        if on { played.insert(t.itemKey); Library.shared.resume[t.itemKey] = nil } else { played.remove(t.itemKey) }
        d.set(Array(played.suffix(2000)), forKey: "sevbify.played")
    }
}

struct PodcastsPage: View {
    @EnvironmentObject var nav: Nav
    @EnvironmentObject var lib: Library
    @ObservedObject var shows = Shows.shared
    @State private var query = ""
    @State private var top: [ShowRef] = []
    @State private var found: [ShowRef] = []
    @State private var busy = false
    @State private var error = ""

    private var country: String { (Locale.current.region?.identifier ?? "US").lowercased() }

    var body: some View {
        List {
            Section {
                TextField("Search podcasts", text: $query).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .onSubmit { Task { await search() } }
            }
            if !shows.saved.isEmpty {
                Button { nav.go(.songs("Your Episodes", shows.saved)) } label: {
                    Label("Your Episodes (\(shows.saved.count))", systemImage: "bookmark.fill").foregroundColor(C.green)
                }
            }
            if busy { ProgressView() }
            if !error.isEmpty { Text(error).font(.caption).foregroundColor(C.dim) }
            if !found.isEmpty {
                Section("Results") { ForEach(found, id: \.key) { s in row(s) } }
            }
            if !shows.followed.isEmpty {
                Section("Following") { ForEach(shows.followed, id: \.key) { s in row(s) } }
            }
            if !top.isEmpty {
                Section("Top podcasts") { ForEach(top, id: \.key) { s in row(s) } }
            }
        }
        .listStyle(.plain).scrollContentBackground(.hidden).background(C.bg.ignoresSafeArea())
        .navigationTitle("Podcasts")
        .task {
            guard top.isEmpty, lib.settings.online else { return }
            top = ((try? await Bridge.list("top_shows", [country])) ?? []).map(ShowRef.init)
        }
    }

    private func row(_ s: ShowRef) -> some View {
        Button { nav.go(.show(s)) } label: {
            HStack(spacing: 12) {
                Cover(url: s.image, size: 56)
                VStack(alignment: .leading, spacing: 2) {
                    Text(s.title).lineLimit(2)
                    Text(s.author).font(.caption).foregroundColor(C.dim).lineLimit(1)
                }
            }
        }.buttonStyle(.plain).listRowBackground(C.bg)
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { found = []; return }
        busy = true; error = ""
        defer { busy = false }
        if q.hasPrefix("https://"), let o = try? await Bridge.object("show_link", [q]), !o.isEmpty {
            found = [ShowRef(o)]; return
        }
        do { found = try await Bridge.list("search_podcasts", [q, country, true]).map(ShowRef.init) }
        catch { self.error = "Search didn't work: \(error.localizedDescription)" }
        if found.isEmpty && error.isEmpty { error = "No podcasts found for “\(q)”." }
    }
}

struct ShowPage: View {
    let show: ShowRef
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @ObservedObject var shows = Shows.shared
    @State private var episodes: [(track: Track, date: String, description: String)] = []
    @State private var note = ""
    @State private var state = "Loading episodes…"
    @State private var filter = ""

    var body: some View {
        let tracks = episodes.map(\.track)
        List {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 14) {
                    Cover(url: show.image, size: 110, corner: 8)
                    VStack(alignment: .leading, spacing: 6) {
                        Text(show.title).font(.title3.bold()).lineLimit(3)
                        Text(show.author).font(.subheadline).foregroundColor(C.dim).lineLimit(2)
                    }
                }
                HStack {
                    Button(shows.isFollowed(show) ? "Following" : "Follow") { shows.toggleFollow(show) }
                        .buttonStyle(.bordered).tint(shows.isFollowed(show) ? C.green : .white)
                    Spacer()
                    if let first = episodes.first(where: { !shows.isPlayed($0.track) })?.track ?? tracks.first {
                        Button { player.play(first, in: tracks, source: show.title) } label: {
                            Image(systemName: "play.circle.fill").font(.system(size: 44)).foregroundColor(C.green)
                        }.accessibilityLabel("Play")
                    }
                }
                if !note.isEmpty { Text(note).font(.caption).foregroundColor(C.dim) }
            }.listRowBackground(C.bg)
            if episodes.count > 8 {
                TextField("Find in episodes", text: $filter).listRowBackground(C.bg)
            }
            if episodes.isEmpty { Text(state).foregroundColor(C.dim).listRowBackground(C.bg) }
            ForEach(Array(episodes.enumerated()).filter { filter.isEmpty || $0.element.track.title.localizedCaseInsensitiveContains(filter) },
                    id: \.offset) { _, e in
                episodeRow(e.track, e.date, e.description, tracks)
            }
        }
        .listStyle(.plain).scrollContentBackground(.hidden).background(C.bg.ignoresSafeArea())
        .navigationTitle(show.title).navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func episodeRow(_ t: Track, _ date: String, _ description: String, _ all: [Track]) -> some View {
        let playing = player.current?.itemKey == t.itemKey
        let left: Int? = lib.resume[t.itemKey].flatMap { r in t.durationMs > 0 ? max(0, t.durationMs / 1000 - Int(r)) : nil }
        let bits = [date, left.map { "\($0 / 60) min left" } ?? (t.durationMs > 0 ? "\(t.durationMs / 60000) min" : ""),
                    shows.isPlayed(t) ? "Played" : ""].filter { !$0.isEmpty }
        return VStack(alignment: .leading, spacing: 6) {
            Text(t.title).font(.subheadline.bold()).foregroundColor(playing ? C.green : C.text).lineLimit(2)
            if !description.isEmpty { Text(description).font(.caption).foregroundColor(C.dim).lineLimit(2) }
            HStack {
                Text(bits.joined(separator: " • ")).font(.caption).foregroundColor(C.dim)
                Spacer()
                Button { shows.toggleSaved(t) } label: {
                    Image(systemName: shows.isSaved(t) ? "checkmark.circle.fill" : "plus.circle")
                        .foregroundColor(shows.isSaved(t) ? C.green : C.dim)
                }.buttonStyle(.plain).accessibilityLabel(shows.isSaved(t) ? "Remove from Your Episodes" : "Save to Your Episodes")
                Button { player.play(t, in: all, source: show.title) } label: {
                    Image(systemName: "play.circle.fill").font(.title2).foregroundColor(.white)
                }.buttonStyle(.plain).accessibilityLabel("Play")
            }
        }
        .padding(.vertical, 6).listRowBackground(C.bg)
        .contextMenu {
            Button(shows.isPlayed(t) ? "Mark as not played" : "Mark as played") { shows.setPlayed(t, !shows.isPlayed(t)) }
            Button(shows.isSaved(t) ? "Remove from Your Episodes" : "Save to Your Episodes") { shows.toggleSaved(t) }
            Button("Add to queue") { player.addToQueue(t) }
        }
    }

    private func load() async {
        guard episodes.isEmpty else { return }
        do {
            let o = try await Bridge.object("fetch_show", [show.json])
            note = o["note"] as? String ?? ""
            episodes = (o["episodes"] as? [[String: Any]] ?? []).map { e in
                (Track(dict: e["track"] as? [String: Any] ?? [:]), e["date"] as? String ?? "", e["description"] as? String ?? "")
            }
            if episodes.isEmpty { state = "No episodes found." }
        } catch { state = "Couldn't load this show: \(error.localizedDescription)" }
    }
}
