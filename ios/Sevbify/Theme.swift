import SwiftUI

/// Spotify-like dark look, same colours as the other Sevbify apps.
enum C {
    static let bg = Color(red: 0.07, green: 0.07, blue: 0.07)
    static let card = Color(red: 0.16, green: 0.16, blue: 0.16)
    static let elevated = Color(red: 0.11, green: 0.11, blue: 0.11)
    static let green = Color(red: 0.12, green: 0.84, blue: 0.38)
    static let text = Color.white
    static let dim = Color(white: 0.70)
}

/// Where a list or page goes when tapped.
enum Route: Hashable {
    case playlist(String)
    case yourSongs
    case artist(String)
    case album(AlbumRef)
    case genre(Int, String)
    case songs(String, [Track])
    case radio(String, [Track])
    case settings
    case importLink
    case downloads
}

struct AlbumRef: Hashable {
    var id: String
    var title: String
    var artist: String
    var cover: String
    init(_ d: [String: Any]) {
        id = "\(d["id"] ?? "")"; title = d["title"] as? String ?? ""
        artist = (d["artist"] as? [String: Any])?["name"] as? String ?? ""
        cover = d["cover_xl"] as? String ?? d["cover_big"] as? String ?? d["cover_medium"] as? String ?? ""
    }
    var dict: [String: Any] {
        ["id": Int(id) ?? id, "title": title, "artist": ["name": artist], "cover_xl": cover]
    }
}

struct Cover: View {
    let url: String
    var size: CGFloat
    var corner: CGFloat = 4
    var body: some View {
        Group {
            if let u = URL(string: url), !url.isEmpty {
                AsyncImage(url: u, transaction: Transaction(animation: .easeIn(duration: 0.15))) { phase in
                    if let img = phase.image { img.resizable().scaledToFill() } else { placeholder }
                }
            } else { placeholder }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: corner))
    }
    private var placeholder: some View {
        ZStack { C.card; Image(systemName: "music.note").font(.system(size: size * 0.35)).foregroundColor(C.dim) }
    }
}

/// Colours for Settings ▸ "Show where playlists came from" (same as Windows and Android).
func originColour(_ origin: String) -> Color {
    switch origin {
    case "file": return Color(red: 0.31, green: 0.61, blue: 0.96)          // imported from a file: blue
    case "spotify", "link": return C.green                                 // Spotify link: green
    case "apple": return .white                                            // Apple Music link: white
    case "deezer": return Color(red: 0.64, green: 0.22, blue: 1.0)         // Deezer link: purple
    case "jamendo": return Color(red: 1.0, green: 0.54, blue: 0.12)        // Jamendo link: orange
    default: return Color(white: 0.54)                                     // made in Sevbify: grey
    }
}

struct PlaylistCover: View {
    let playlist: Playlist
    var size: CGFloat
    @EnvironmentObject var lib: Library
    var body: some View {
        let covers = playlist.covers
        ZStack {
            if covers.count == 4 {
                VStack(spacing: 0) {
                    HStack(spacing: 0) { Cover(url: covers[0], size: size / 2, corner: 0); Cover(url: covers[1], size: size / 2, corner: 0) }
                    HStack(spacing: 0) { Cover(url: covers[2], size: size / 2, corner: 0); Cover(url: covers[3], size: size / 2, corner: 0) }
                }
            } else {
                Cover(url: covers.first ?? "", size: size, corner: 0)
            }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .overlay {
            if lib.settings.showPlaylistOrigin {
                RoundedRectangle(cornerRadius: 4).stroke(originColour(playlist.origin), lineWidth: size >= 100 ? 4 : 2)
            }
        }
    }
}

struct SectionTitle: View {
    let text: String
    init(_ t: String) { text = t }
    var body: some View {
        Text(text).font(.title2.bold()).foregroundColor(C.text).frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16).padding(.top, 20).padding(.bottom, 8)
    }
}

/// One song in a list: cover, title, artist, a green ⬇ when it's on this iPhone, and the ••• menu.
struct TrackRow: View {
    let track: Track
    var showCover = true
    var playlistId: String? = nil
    var onTap: () -> Void
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @EnvironmentObject var downloads: Downloads
    @State private var menu = false

    var body: some View {
        let playing = player.current?.matchKey == track.matchKey && !player.context.isEmpty
        HStack(spacing: 12) {
            if showCover { Cover(url: track.art, size: 48) }
            VStack(alignment: .leading, spacing: 3) {
                Text(track.title).lineLimit(1).foregroundColor(playing ? C.green : C.text)
                HStack(spacing: 4) {
                    if lib.isDownloaded(track) {
                        Image(systemName: "arrow.down.circle.fill").font(.caption2).foregroundColor(C.green)
                    } else if let st = downloads.state(of: track), st == "Downloading" || st == "Waiting" {
                        ProgressView().scaleEffect(0.5).frame(width: 12, height: 12)
                    }
                    if track.explicit {
                        Text("E").font(.system(size: 9, weight: .bold)).foregroundColor(.black)
                            .padding(.horizontal, 3).background(C.dim).cornerRadius(2)
                    }
                    Text(track.artist).font(.subheadline).foregroundColor(C.dim).lineLimit(1)
                }
            }
            Spacer(minLength: 0)
            Button { menu = true } label: {
                Image(systemName: "ellipsis").foregroundColor(C.dim).frame(width: 36, height: 36)
            }.buttonStyle(.plain).accessibilityLabel("More")
        }
        .padding(.horizontal, 16).padding(.vertical, 6)
        .contentShape(Rectangle())
        .onTapGesture(perform: onTap)
        .sheet(isPresented: $menu) { TrackMenu(track: track, playlistId: playlistId).presentationDetents([.medium, .large]) }
    }
}

/// Spotify's song menu (bottom sheet).
struct TrackMenu: View {
    let track: Track
    var playlistId: String? = nil
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @Environment(\.dismiss) var dismiss
    @State private var choosing = false
    @State private var previewing = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 12) {
                Cover(url: track.art, size: 56)
                VStack(alignment: .leading) {
                    Text(track.title).font(.headline).lineLimit(1)
                    Text(track.artist).font(.subheadline).foregroundColor(C.dim).lineLimit(1)
                }
            }.padding(16)
            Divider().background(C.card)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    item("plus.circle", "Add to playlist") { choosing = true }
                    item("text.line.first.and.arrowtriangle.forward", "Play next") { player.playNext(track); dismiss() }
                    item("text.append", "Add to queue") { player.addToQueue(track); dismiss() }
                    if !lib.isDownloaded(track) && !track.isItem {
                        item("arrow.down.circle", "Download") { Downloads.shared.download([track]); dismiss() }
                    }
                    if let pid = playlistId {
                        item("minus.circle", "Remove from this playlist") {
                            lib.update(pid) { $0.tracks.removeAll { $0.uid == track.uid } }; dismiss()
                        }
                    }
                    if !track.isItem {
                        item("dot.radiowaves.left.and.right", "Go to song radio") { player.startRadio(track); dismiss() }
                        item("play.circle", "Preview (30 s)") { previewing = true }
                        item("person", "Go to artist") { dismiss(); nav.go(.artist(track.artist)) }
                        item("square.and.arrow.up", "Share") { share(); dismiss() }
                    }
                }
            }
        }
        .background(C.elevated.ignoresSafeArea())
        .foregroundColor(C.text)
        .sheet(isPresented: $choosing) { AddToPlaylistSheet(tracks: [track]) { dismiss() } }
        .sheet(isPresented: $previewing) { PreviewView(track: track) }
    }

    private func item(_ icon: String, _ label: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: icon).frame(width: 24).foregroundColor(C.dim)
                Text(label)
                Spacer()
            }.padding(.horizontal, 20).padding(.vertical, 14).contentShape(Rectangle())
        }.buttonStyle(.plain)
    }

    /// Sevbify has no accounts: a song is shared as a Spotify/YouTube link (exact when song.link finds it).
    private func share() {
        let t = track
        Task {
            var text = "\(t.title) by \(t.artist)"
            if let o = try? await Bridge.object("share_links", [t.artist, t.title, t.pageUrl, ""]) {
                let link = (o["songlink"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? (o["spotify"] as? String ?? "")
                text += "\n" + link
            }
            await MainActor.run { Share.present([text]) }
        }
    }
}

enum Share {
    @MainActor static func present(_ items: [Any]) {
        guard let root = UIApplication.shared.connectedScenes.compactMap({ ($0 as? UIWindowScene)?.keyWindow }).first?.rootViewController
        else { return }
        var top = root
        while let p = top.presentedViewController { top = p }
        let vc = UIActivityViewController(activityItems: items, applicationActivities: nil)
        vc.popoverPresentationController?.sourceView = top.view
        top.present(vc, animated: true)
    }
}

struct AddToPlaylistSheet: View {
    let tracks: [Track]
    var done: () -> Void = {}
    @EnvironmentObject var lib: Library
    @EnvironmentObject var player: Player
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationStack {
            List {
                Button {
                    let pl = lib.newPlaylist(tracks: tracks)
                    player.status = "Added to \(pl.name)"; dismiss(); done()
                } label: { Label("New playlist", systemImage: "plus") }
                ForEach(lib.playlists) { pl in
                    Button {
                        lib.add(tracks, to: pl.id); player.status = "Added to \(pl.name)"; dismiss(); done()
                    } label: {
                        HStack { PlaylistCover(playlist: pl, size: 44); Text(pl.name).foregroundColor(C.text) }
                    }
                }
            }
            .scrollContentBackground(.hidden).background(C.elevated)
            .navigationTitle("Add to playlist").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
    }
}
