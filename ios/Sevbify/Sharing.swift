import SwiftUI

/// Collaborative playlists and Blend on iPhone, like the PC and Android (core/share_playlist.py): a playlist or your
/// taste goes into a sevbify:// link you send however you like. Nothing is uploaded anywhere. Opening a link fills in
/// Import a playlist, so you see what it is before anything is added.
@MainActor
final class Sharing: ObservableObject {
    static let shared = Sharing()
    @Published var pending = ""                // a link opened from another app, waiting in Import a playlist

    func open(_ url: URL) {
        guard url.scheme == "sevbify", url.host == "playlist" || url.host == "taste" else { return }
        pending = String(url.absoluteString.prefix(400_000))
        Nav.current?.tab = .library
        Nav.current?.library.append(Route.importLink)
    }

    func sharePlaylist(_ pl: Playlist) {
        Task {
            let tracks = pl.tracks.map(\.dict)
            guard let data = try? JSONSerialization.data(withJSONObject: tracks),
                  let link = try? await Bridge.call("share_link", [pl.name, String(decoding: data, as: UTF8.self)]) as? String
            else { Player.shared.status = "Couldn't make the link"; return }
            Share.present(["Here's my playlist “\(pl.name)” for Sevbify (paste it in Import a playlist):\n\(link)"])
        }
    }

    func shareTaste() {
        Task {
            guard let link = try? await Bridge.call("taste_link", [Listens.json()]) as? String else {
                Player.shared.status = "Couldn't make the link"; return
            }
            Share.present(["Let's make a Blend in Sevbify (paste this in Import a playlist, then send me yours):\n\(link)"])
        }
    }
}

/// What you've played on this iPhone ([artist, title, time]), kept here only: for Blend. Last 5000; not while a
/// private session is on.
enum Listens {
    private static let key = "sevbify.listens"
    static func record(_ t: Track) {
        guard !t.isItem else { return }
        var rows = all()
        rows.append([String(t.artist.prefix(200)), String(t.title.prefix(300)), Int(Date().timeIntervalSince1970)])
        if rows.count > 5000 { rows.removeFirst(rows.count - 5000) }
        if let data = try? JSONSerialization.data(withJSONObject: rows) { UserDefaults.standard.set(data, forKey: key) }
    }
    static func all() -> [[Any]] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let rows = try? JSONSerialization.jsonObject(with: data) as? [[Any]] else { return [] }
        return rows
    }
    static func json() -> String {
        (try? JSONSerialization.data(withJSONObject: all())).map { String(decoding: $0, as: UTF8.self) } ?? "[]"
    }
}

/// Your listening stats ("Wrapped"), worked out on this iPhone from what you've played (core/wrapped.py).
struct WrappedView: View {
    @Environment(\.dismiss) var dismiss
    @State private var period = "This year"
    @State private var st: [String: Any]?
    var body: some View {
        NavigationStack {
            List {
                Picker("Period", selection: $period) {
                    ForEach(["4 weeks", "6 months", "This year", "All time"], id: \.self) { Text($0) }
                }.pickerStyle(.segmented)
                if let s = st {
                    if (s["plays"] as? Int ?? 0) == 0 {
                        Text("Nothing played in this period yet.")
                    } else {
                        VStack(alignment: .leading) {
                            Text("\(s["minutes"] as? Int ?? 0)").font(.system(size: 44, weight: .heavy))
                            Text("minutes · \(s["plays"] as? Int ?? 0) plays · \(s["artists"] as? Int ?? 0) artists").foregroundColor(C.dim)
                        }
                        Section("Top artists") {
                            ForEach(Array((s["top_artists"] as? [[String: Any]] ?? []).enumerated()), id: \.offset) { i, a in
                                Text("\(i + 1). \(a["artist"] as? String ?? "")  ·  \(a["plays"] as? Int ?? 0) plays")
                            }
                        }
                        Section("Top songs") {
                            ForEach(Array((s["top_songs"] as? [[String: Any]] ?? []).enumerated()), id: \.offset) { i, t in
                                Text("\(i + 1). \(t["title"] as? String ?? "") · \(t["artist"] as? String ?? "")")
                            }
                        }
                    }
                } else { Text("Working it out…") }
                Text("Worked out on this iPhone from what you've played; nothing is sent anywhere.").font(.caption).foregroundColor(C.dim)
            }
            .navigationTitle("Your Wrapped")
            .toolbar { Button("Close") { dismiss() } }
            .task(id: period) { st = try? await Bridge.object("wrapped", [Listens.json(), period]) }
        }
        .preferredColorScheme(.dark)
    }
}
