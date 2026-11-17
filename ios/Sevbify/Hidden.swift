import SwiftUI

/// Hide song / Don't play this artist, like the PC (core/hidden.py) and Android: skipped when music plays by itself
/// (playlists, albums, radio, autoplay); a song you pick or queue yourself still plays. Kept on this iPhone.
/// Settings → Hidden songs and artists lists them with a switch each.
final class Hidden: ObservableObject {
    static let shared = Hidden()
    struct Entry: Codable, Identifiable, Equatable {
        var kind: String          // "song" | "artist"
        var key: String
        var artist: String
        var title: String
        var on: Bool
        var id: String { kind + ":" + key }
    }
    @Published private(set) var entries: [Entry] = []
    @Published var noteSeen = false { didSet { save() } }
    private let storeKey = "sevbify.hidden"
    private static let maxEntries = 2000

    private init() {
        if let data = UserDefaults.standard.data(forKey: storeKey),
           let saved = try? JSONDecoder().decode(Saved.self, from: data) {
            entries = Array(saved.entries.filter { !$0.key.trimmingCharacters(in: CharacterSet(charactersIn: "|")).isEmpty }
                .prefix(Self.maxEntries))
            noteSeen = saved.noteSeen
        }
    }

    private struct Saved: Codable { var entries: [Entry]; var noteSeen: Bool }

    private func save() {
        if let data = try? JSONEncoder().encode(Saved(entries: entries, noteSeen: noteSeen)) {
            UserDefaults.standard.set(data, forKey: storeKey)
        }
    }

    static func norm(_ s: String) -> String {
        let folded = s.precomposedStringWithCompatibilityMapping.lowercased()
        return folded.components(separatedBy: CharacterSet.alphanumerics.inverted).filter { !$0.isEmpty }.joined(separator: " ")
    }
    static func songKey(_ artist: String, _ title: String) -> String { norm(artist) + "|" + norm(title) }

    func isHidden(_ t: Track) -> Bool {
        if t.isItem { return false }
        let artists = Set(entries.filter { $0.on && $0.kind == "artist" }.map(\.key))
        if !artists.isEmpty {
            if artists.contains(Self.norm(t.artist)) { return true }
            let parts = t.artist.replacingOccurrences(of: " feat. ", with: ",").replacingOccurrences(of: " ft. ", with: ",")
                .replacingOccurrences(of: "&", with: ",").components(separatedBy: ",")
            if parts.contains(where: { artists.contains(Self.norm($0)) && !Self.norm($0).isEmpty }) { return true }
        }
        let k = Self.songKey(t.artist, t.title)
        return entries.contains { $0.on && $0.kind == "song" && $0.key == k }
    }

    func songHidden(_ t: Track) -> Bool { entries.contains { $0.on && $0.kind == "song" && $0.key == Self.songKey(t.artist, t.title) } }
    func artistHidden(_ a: String) -> Bool { entries.contains { $0.on && $0.kind == "artist" && $0.key == Self.norm(a) } }

    func set(_ kind: String, artist: String, title: String = "", on: Bool) {
        let key = kind == "song" ? Self.songKey(artist, title) : Self.norm(artist)
        guard !key.trimmingCharacters(in: CharacterSet(charactersIn: "|")).isEmpty else { return }
        if let i = entries.firstIndex(where: { $0.kind == kind && $0.key == key }) {
            entries[i].on = on
        } else if on {
            entries.append(Entry(kind: kind, key: key, artist: String(artist.prefix(200)), title: String(title.prefix(300)), on: true))
            if entries.count > Self.maxEntries { entries.removeFirst(entries.count - Self.maxEntries) }
        }
        save()
    }

    func remove(_ e: Entry) { entries.removeAll { $0.id == e.id }; save() }
}

struct HiddenSection: View {
    @ObservedObject var hidden = Hidden.shared
    var body: some View {
        Section("Hidden songs and artists") {
            if hidden.entries.isEmpty {
                Text("Nothing hidden. A song's ••• menu has Hide song and Don't play this artist: they're then skipped in playlists, albums, radio and mixes, and come back here with one switch.")
                    .font(.caption).foregroundColor(C.dim)
            } else {
                ForEach(hidden.entries.reversed().prefix(300)) { e in
                    HStack {
                        Text(e.kind == "song" ? "\(e.title) · \(e.artist)" : "\(e.artist) (artist)").font(.subheadline)
                        Spacer()
                        Toggle("", isOn: Binding(get: { e.on }, set: { hidden.set(e.kind, artist: e.artist, title: e.title, on: $0) }))
                            .labelsHidden().tint(C.green)
                    }
                    .swipeActions { Button("Remove", role: .destructive) { hidden.remove(e) } }
                }
                Text("On = skipped when music plays by itself. Swipe left to remove one.").font(.caption).foregroundColor(C.dim)
            }
        }
    }
}
