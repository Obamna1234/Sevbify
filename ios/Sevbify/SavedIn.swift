import SwiftUI

/// Spotify's ⊕ / ✓ (the same on the computer and Android): the first tap saves a song to Liked Songs; once it's
/// saved somewhere, the tap opens "Saved in", where you tick or untick Liked Songs and any of your playlists.
/// Episodes and audiobook chapters go to Your Episodes instead.
@MainActor
enum SaveButton {
    static func isSaved(_ t: Track) -> Bool {
        if t.isItem { return Shows.shared.isSaved(t) }
        return Library.shared.playlists.contains { pl in pl.tracks.contains { $0.matchKey == t.matchKey } }
    }
    /// true: show the "Saved in" sheet.
    static func tap(_ t: Track) -> Bool {
        if t.isItem { Shows.shared.toggleSaved(t); return false }
        if !isSaved(t) { Library.shared.toggleLike(t); Player.shared.status = "Added to Liked Songs"; return false }
        return true
    }
}

struct SavedInView: View {
    let track: Track
    @EnvironmentObject var lib: Library
    @Environment(\.dismiss) var dismiss
    @State private var start: Set<String> = []
    @State private var ticked: Set<String> = []
    @State private var likeOn = false
    @State private var find = ""

    var body: some View {
        NavigationStack {
            List {
                Button { likeOn.toggle() } label: {
                    row(cover: AnyView(ZStack { RoundedRectangle(cornerRadius: 4).fill(Color(red: 0.31, green: 0.22, blue: 0.63))
                                               Image(systemName: "heart.fill").foregroundColor(.white) }.frame(width: 48, height: 48)),
                        name: "Liked Songs", sub: "\(lib.playlists.first { $0.origin == "liked" }?.tracks.count ?? 0) songs", on: likeOn)
                }.buttonStyle(.plain).listRowBackground(C.elevated)
                Section {
                    ForEach(lib.playlists.filter { $0.origin != "liked" && (find.isEmpty || $0.name.localizedCaseInsensitiveContains(find)) }) { pl in
                        Button { if ticked.contains(pl.id) { ticked.remove(pl.id) } else { ticked.insert(pl.id) } } label: {
                            row(cover: AnyView(PlaylistCover(playlist: pl, size: 48)), name: pl.name, sub: "\(pl.tracks.count) songs",
                                on: ticked.contains(pl.id))
                        }.buttonStyle(.plain).listRowBackground(C.elevated)
                    }
                }
            }
            .searchable(text: $find, prompt: "Find playlist")
            .listStyle(.plain).scrollContentBackground(.hidden).background(C.elevated)
            .navigationTitle("Saved in").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .primaryAction) {
                    Button("New playlist") {
                        let pl = lib.newPlaylist(nil, tracks: [track.fresh()])
                        start.insert(pl.id); ticked.insert(pl.id)
                    }.tint(C.green)
                }
            }
            .safeAreaInset(edge: .bottom) {
                Button { done() } label: {
                    Text("Done").bold().foregroundColor(.black).padding(.horizontal, 32).padding(.vertical, 12)
                        .background(Capsule().fill(C.green))
                }.padding(.bottom, 8)
            }
        }
        .onAppear {
            start = Set(lib.playlists.filter { $0.origin != "liked" && $0.tracks.contains { $0.matchKey == track.matchKey } }.map(\.id))
            ticked = start
            likeOn = lib.isLiked(track)
        }
    }

    private func row(cover: AnyView, name: String, sub: String, on: Bool) -> some View {
        HStack(spacing: 12) {
            cover
            VStack(alignment: .leading, spacing: 2) {
                Text(name).foregroundColor(C.text).lineLimit(1)
                Text(sub).font(.caption).foregroundColor(C.dim)
            }
            Spacer()
            Image(systemName: on ? "checkmark.circle.fill" : "plus.circle").font(.title2).foregroundColor(on ? C.green : C.dim)
        }.contentShape(Rectangle())
    }

    /// Changes only happen here: Cancel (or swiping the sheet away) leaves everything as it was.
    private func done() {
        if likeOn != lib.isLiked(track) { lib.toggleLike(track) }
        for pl in lib.playlists where pl.origin != "liked" {
            let was = start.contains(pl.id), now = ticked.contains(pl.id)
            if now && !was { lib.add([track], to: pl.id) }
            if was && !now { lib.update(pl.id) { $0.tracks.removeAll { $0.matchKey == track.matchKey } } }
        }
        dismiss()
    }
}
