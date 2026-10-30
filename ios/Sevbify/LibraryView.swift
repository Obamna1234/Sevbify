import SwiftUI
import UniformTypeIdentifiers

struct LibraryView: View {
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @EnvironmentObject var downloads: Downloads
    @State private var creating = false
    @State private var newName = ""
    @State private var pickingFolder = false
    @State private var filter = ""

    var body: some View {
        List {
            Section {
                row(icon: AnyView(LinearGradient(colors: [Color(red: 0.27, green: 0.04, blue: 0.96), Color(red: 0.77, green: 0.94, blue: 0.85)], startPoint: .topLeading, endPoint: .bottomTrailing).overlay(Image(systemName: "heart.fill").foregroundColor(.white))),
                    title: "Your Songs", subtitle: "\(lib.localSongs.count) songs on this iPhone") { nav.go(.yourSongs) }
                if downloads.active > 0 || !downloads.jobs.isEmpty {
                    row(icon: AnyView(C.card.overlay(Image(systemName: "arrow.down.circle").foregroundColor(C.green))),
                        title: "Downloads", subtitle: downloads.active > 0 ? "\(downloads.active) waiting or downloading" : "Finished") { nav.go(.downloads) }
                }
                ForEach(lib.playlists.filter { filter.isEmpty || $0.name.lowercased().contains(filter.lowercased()) }) { pl in
                    Button { nav.go(.playlist(pl.id)) } label: {
                        HStack(spacing: 12) {
                            PlaylistCover(playlist: pl, size: 64)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(pl.name).lineLimit(1)
                                HStack(spacing: 4) {
                                    if pl.pinned { Image(systemName: "pin.fill").font(.caption2).foregroundColor(C.green) }
                                    if !pl.tracks.isEmpty && pl.tracks.allSatisfy({ lib.isDownloaded($0) }) {
                                        Image(systemName: "arrow.down.circle.fill").font(.caption2).foregroundColor(C.green)
                                    }
                                    Text("Playlist • \(pl.tracks.count) songs").font(.caption).foregroundColor(C.dim)
                                }
                            }
                        }
                    }.buttonStyle(.plain)
                    .swipeActions {
                        Button(role: .destructive) { lib.delete(pl.id) } label: { Label("Delete", systemImage: "trash") }
                    }
                }
            }
            .listRowBackground(C.bg)
            .listRowSeparator(.hidden)

            Section("Folders you added") {
                ForEach(lib.folders) { f in
                    Label(f.name, systemImage: "folder").swipeActions {
                        Button(role: .destructive) { lib.removeFolder(f) } label: { Label("Remove", systemImage: "minus.circle") }
                    }
                }
                Button { pickingFolder = true } label: { Label("Add a folder from Files", systemImage: "folder.badge.plus") }
                Text("Sevbify only reads folders you add. You can also put songs in Files ▸ On My iPhone ▸ Sevbify.")
                    .font(.caption).foregroundColor(C.dim)
            }
            .listRowBackground(C.bg)
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(C.bg.ignoresSafeArea())
        .navigationTitle("Your Library")
        .searchable(text: $filter, prompt: "Find in playlists")
        .refreshable { await lib.scan() }
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Button { newName = ""; creating = true } label: { Label("Playlist", systemImage: "music.note.list") }
                    Button { nav.go(.importLink) } label: { Label("Import a playlist", systemImage: "link") }
                } label: { Image(systemName: "plus").font(.title3) }.accessibilityLabel("Create")
            }
            ToolbarItem(placement: .navigationBarLeading) {
                Button { nav.go(.settings) } label: { Image(systemName: "gearshape") }.accessibilityLabel("Settings")
            }
        }
        .alert("Name your playlist", isPresented: $creating) {
            TextField("My Playlist", text: $newName)
            Button("Create") { let pl = lib.newPlaylist(newName); nav.go(.playlist(pl.id)) }
            Button("Cancel", role: .cancel) {}
        }
        .fileImporter(isPresented: $pickingFolder, allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result { lib.addFolder(url) }
        }
    }

    private func row(icon: AnyView, title: String, subtitle: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                icon.frame(width: 64, height: 64).cornerRadius(4)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                    Text(subtitle).font(.caption).foregroundColor(C.dim)
                }
            }
        }.buttonStyle(.plain)
    }
}

/// The page shared by playlists, albums, Your Songs...: Spotify's phone layout.
struct SongsPage: View {
    let title: String
    var subtitle = ""
    let cover: String
    let tracks: [Track]
    let source: String
    var kind = "Playlist"
    var playlist: Playlist? = nil
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @EnvironmentObject var downloads: Downloads
    @State private var askDownload = false

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                HStack {
                    Spacer()
                    if let pl = playlist { PlaylistCover(playlist: pl, size: 230) }
                    else if kind == "Radio" { RadioCover(title: title, cover: cover, size: 230) }
                    else { Cover(url: cover, size: 230) }
                    Spacer()
                }.padding(.top, 8)
                Text(title).font(.title.bold()).padding(.horizontal, 16).padding(.top, 16)
                if !subtitle.isEmpty { Text(subtitle).font(.subheadline.bold()).padding(.horizontal, 16).padding(.top, 2) }
                Text([kind, "\(tracks.count) songs", formatTotal(tracks.reduce(0) { $0 + $1.durationMs })].joined(separator: " • "))
                    .font(.caption).foregroundColor(C.dim).padding(.horizontal, 16).padding(.top, 4)
                HStack(spacing: 20) {
                    let pending = tracks.filter { !lib.isDownloaded($0) && !$0.isItem }
                    Button { if !pending.isEmpty { askDownload = true } } label: {
                        Image(systemName: pending.isEmpty && !tracks.isEmpty ? "arrow.down.circle.fill" : "arrow.down.circle")
                            .font(.title2).foregroundColor(pending.isEmpty && !tracks.isEmpty ? C.green : C.dim)
                    }.accessibilityLabel("Download")
                    Spacer()
                    Button { player.playAll(tracks, source: source, shuffled: true) } label: {
                        Image(systemName: "shuffle").font(.title2).foregroundColor(player.shuffle ? C.green : C.dim)
                    }.accessibilityLabel("Shuffle")
                    Button { player.playAll(tracks, source: source, shuffled: false) } label: {
                        Image(systemName: "play.fill").font(.title2).foregroundColor(.black).frame(width: 56, height: 56)
                            .background(Circle().fill(C.green))
                    }.accessibilityLabel("Play")
                }.padding(16)
                ForEach(tracks) { t in TrackRow(track: t, playlistId: playlist?.id) { player.play(t, in: tracks, source: source) } }
                if tracks.isEmpty {
                    Text(playlist != nil ? "Let's find something for your playlist: search for songs and use ••• ▸ Add to playlist."
                         : "Nothing here yet.").foregroundColor(C.dim).padding(16)
                }
                Spacer(minLength: 24)
            }
        }
        .background(C.bg.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog("Download", isPresented: $askDownload) {
            let pending = tracks.filter { !lib.isDownloaded($0) && !$0.isItem }
            Button("Download all \(pending.count) songs") { downloads.download(pending) }
            Button("Cancel", role: .cancel) {}
        }
    }
}

struct PlaylistPage: View {
    let id: String
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @State private var renaming = false
    @State private var newName = ""

    var body: some View {
        Group {
            if let pl = lib.playlist(id) {
                SongsPage(title: pl.name, cover: pl.coverUrl, tracks: pl.tracks, source: pl.name, playlist: pl)
                    .toolbar {
                        Menu {
                            Button { newName = pl.name; renaming = true } label: { Label("Rename", systemImage: "pencil") }
                            Button { lib.update(id) { $0.pinned.toggle() } } label: {
                                Label(pl.pinned ? "Unpin" : "Pin", systemImage: "pin")
                            }
                            Button(role: .destructive) { lib.delete(id); nav.library = NavigationPath() } label: {
                                Label("Delete playlist", systemImage: "trash")
                            }
                        } label: { Image(systemName: "ellipsis") }
                    }
                    .onAppear { lib.update(id) { $0.lastPlayed = Date().timeIntervalSince1970 } }
            } else {
                Text("This playlist was deleted.").foregroundColor(C.dim)
            }
        }
        .alert("Rename playlist", isPresented: $renaming) {
            TextField("Name", text: $newName)
            Button("Save") { if !newName.trimmingCharacters(in: .whitespaces).isEmpty { lib.update(id) { $0.name = newName } } }
            Button("Cancel", role: .cancel) {}
        }
    }
}

struct YourSongsPage: View {
    @EnvironmentObject var lib: Library
    var body: some View {
        SongsPage(title: "Your Songs", cover: "", tracks: lib.localSongs, source: "Your Songs", kind: "On this iPhone")
            .overlay { if lib.scanning && lib.localSongs.isEmpty { ProgressView() } }
    }
}

struct DownloadsPage: View {
    @EnvironmentObject var downloads: Downloads
    var body: some View {
        List {
            ForEach(downloads.jobs.reversed()) { j in
                HStack {
                    Cover(url: j.track.art, size: 44)
                    VStack(alignment: .leading) {
                        Text(j.track.title).lineLimit(1)
                        Text(j.state).font(.caption).foregroundColor(j.state.hasPrefix("Failed") ? .red : C.dim).lineLimit(2)
                    }
                    Spacer()
                    if j.state == "Downloading" { ProgressView() }
                }.listRowBackground(C.bg)
            }
        }
        .listStyle(.plain).scrollContentBackground(.hidden).background(C.bg.ignoresSafeArea())
        .navigationTitle("Downloads")
        .toolbar { Button("Clear finished") { downloads.clearFinished() } }
    }
}

/// Import a playlist from a Spotify, Apple Music, Deezer or Jamendo link (no sign-in anywhere).
struct ImportView: View {
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @EnvironmentObject var player: Player
    @State private var link = ""
    @State private var songs = ""
    @State private var busy = false

    var body: some View {
        Form {
            Section {
                TextField("https://open.spotify.com/playlist/…", text: $link).textInputAutocapitalization(.never).autocorrectionDisabled()
                if link.lowercased().contains("jamendo.com") {
                    TextField("Jamendo client ID (free, from devportal.jamendo.com)", text: $lib.settings.jamendoId)
                        .textInputAutocapitalization(.never)
                }
            } header: { Text("Playlist or album link") } footer: {
                Text("A public Spotify, Apple Music, Deezer or Jamendo link. Same order and cover; songs you have play from your iPhone, the rest stream while online. Your accounts are never signed in to.")
            }
            Section {
                TextEditor(text: $songs).frame(minHeight: 100)
            } header: { Text("More than 100 Spotify songs? (optional)") } footer: {
                Text("Spotify only shares 100 songs per link without signing in. In Spotify on a computer, click a song in the playlist, press Ctrl+A then Ctrl+C, and paste the links here.")
            }
            Button(busy ? "Importing…" : "Import") { run() }.disabled(busy || (link.isEmpty && songs.isEmpty))
        }
        .scrollContentBackground(.hidden).background(C.bg.ignoresSafeArea())
        .navigationTitle("Import a playlist")
    }

    private func run() {
        busy = true
        Task {
            do {
                let o = try await Bridge.object("import_link", [link, songs, lib.settings.jamendoId])
                let tracks = (o["tracks"] as? [[String: Any]] ?? []).map(Track.init(dict:))
                var pl = lib.newPlaylist(o["name"] as? String ?? "Imported playlist", tracks: tracks,
                                         origin: o["origin"] as? String ?? "spotify")
                pl.coverUrl = o["cover_url"] as? String ?? ""
                lib.update(pl.id) { $0.coverUrl = pl.coverUrl }
                player.status = "Imported “\(pl.name)”: \(tracks.count) songs" + ((o["truncated"] as? Bool ?? false) ? " (Spotify shares 100 per link)" : "")
                nav.library = NavigationPath()
                nav.tab = .library
                nav.library.append(Route.playlist(pl.id))
            } catch {
                player.status = "Couldn't import: \(error.localizedDescription)"
            }
            busy = false
        }
    }
}


/// A song radio's picture, like Spotify's: the song's cover darkened, with RADIO and the song's name on it.
struct RadioCover: View {
    let title: String
    let cover: String
    let size: CGFloat
    var body: some View {
        ZStack(alignment: .bottomLeading) {
            Cover(url: cover, size: size, corner: 0)
            LinearGradient(colors: [.black.opacity(0.2), .black.opacity(0.8)], startPoint: .top, endPoint: .bottom)
            VStack(alignment: .leading, spacing: 2) {
                Text("RADIO").font(.caption.weight(.heavy)).tracking(2).foregroundColor(C.green)
                Text(title.replacingOccurrences(of: " Radio", with: "")).font(.title2.weight(.heavy)).lineLimit(2)
            }.padding(14)
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}
