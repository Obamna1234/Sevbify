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
