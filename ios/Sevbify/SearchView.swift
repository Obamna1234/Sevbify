import SwiftUI

struct SearchView: View {
    @EnvironmentObject var lib: Library
    @EnvironmentObject var player: Player
    @EnvironmentObject var nav: Nav
    @State private var query = Smoke.initialQuery
    @State private var songs: [Track] = []
    @State private var artists: [[String: Any]] = []
    @State private var genres: [[String: Any]] = []
    @State private var busy = false
    @State private var error = ""
    @State private var searchTask: Task<Void, Never>?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                if query.trimmingCharacters(in: .whitespaces).isEmpty {
                    if !lib.searches.isEmpty {
                        HStack {
                            Text("Recent searches").font(.title3.bold())
                            Spacer()
                            Button("Clear") { lib.searches = []; lib.save() }.foregroundColor(C.dim)
                        }.padding(.horizontal, 16).padding(.top, 16)
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(lib.searches.prefix(10), id: \.self) { q in
                                    Button(q) { query = q }
                                        .padding(.horizontal, 14).padding(.vertical, 7)
                                        .background(Capsule().fill(C.card)).foregroundColor(C.text)
                                }
                            }.padding(.horizontal, 16)
                        }
                    }
                    if lib.settings.online {
                        SectionTitle("Browse all")
                        GenreGrid(genres: genres)
                    }
                } else {
                    let mine = lib.localSongs.filter { matches($0) }
                    if !mine.isEmpty {
                        SectionTitle("Your songs")
                        ForEach(mine.prefix(5)) { t in TrackRow(track: t) { player.play(t, in: mine, source: "Your Songs") } }
                    }
                    if !artists.isEmpty {
                        SectionTitle("Artists")
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 14) {
                                ForEach(Array(artists.prefix(8).enumerated()), id: \.offset) { _, a in
                                    let name = a["name"] as? String ?? ""
                                    Card(title: name, subtitle: "Artist", art: a["picture_xl"] as? String ?? a["picture_big"] as? String ?? "", round: true) {
                                        nav.go(.artist(name))
                                    }
                                }
                            }.padding(.horizontal, 16)
                        }
                    }
                    if !songs.isEmpty {
                        SectionTitle("Songs")
                        ForEach(songs) { t in TrackRow(track: t) { player.play(t, in: songs, source: "Search: \(query)") } }
                    }
                    if busy { ProgressView().frame(maxWidth: .infinity).padding(24) }
                    if !error.isEmpty { Text(error).foregroundColor(C.dim).padding(16) }
                    if !lib.settings.online && mine.isEmpty { Text("You're offline: only your own songs are searched.").foregroundColor(C.dim).padding(16) }
                }
                Spacer(minLength: 24)
            }
        }
        .background(C.bg.ignoresSafeArea())
        .navigationTitle("Search")
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "What do you want to listen to?")
        .autocorrectionDisabled()
        .onChange(of: query) { _ in schedule() }
        .onAppear { if !query.isEmpty && songs.isEmpty { schedule() } }
        .task { if genres.isEmpty && lib.settings.online { genres = (try? await Bridge.list("genres")) ?? [] } }
    }

    private func matches(_ t: Track) -> Bool {
        let q = query.lowercased()
        return t.title.lowercased().contains(q) || t.artist.lowercased().contains(q) || t.album.lowercased().contains(q)
    }

    private func schedule() {
        searchTask?.cancel()
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty, lib.settings.online else { songs = []; artists = []; return }
        searchTask = Task {
            try? await Task.sleep(nanoseconds: 350_000_000)          // wait until typing pauses
            if Task.isCancelled { return }
            busy = true; error = ""
            do {
                async let s = Bridge.tracks("search", [q, 30])
                async let a = Bridge.list("search_artists", [q, 8])
                let (foundSongs, foundArtists) = try await (s, a)
                if Task.isCancelled { return }
                songs = lib.settings.explicitOk ? foundSongs : foundSongs.filter { !$0.explicit }
                artists = foundArtists
            } catch {
                if !Task.isCancelled { self.error = "Search didn't work: \(error.localizedDescription)" }
            }
            busy = false
            // Recent searches: remembered when you stay on the results for a moment (this task is cancelled when you type).
            try? await Task.sleep(nanoseconds: 2_500_000_000)
            if !Task.isCancelled { lib.rememberSearch(q) }
        }
    }
}

struct ArtistPage: View {
    let name: String
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @State private var top: [Track] = []
    @State private var picture = ""
    @State private var bio = ""
    @State private var fans = 0
    @State private var releases: [String: [[String: Any]]] = [:]
    @State private var showAll = false
    @EnvironmentObject var nav: Nav

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                ZStack(alignment: .bottomLeading) {
                    Cover(url: picture, size: UIScreen.main.bounds.width, corner: 0).frame(height: 300).clipped()
                    LinearGradient(colors: [.clear, C.bg], startPoint: .center, endPoint: .bottom)
                    Text(name).font(.system(size: 40, weight: .heavy)).padding(16)
                }.frame(height: 300)
                if fans > 0 { Text("\(fans.formatted()) fans on Deezer").font(.subheadline).foregroundColor(C.dim).padding(.horizontal, 16) }
                HStack {
                    Button { player.startRadio(top.first ?? Track(title: "", artist: name)) } label: {
                        Label("Radio", systemImage: "dot.radiowaves.left.and.right").padding(.horizontal, 14).padding(.vertical, 8)
                            .overlay(Capsule().stroke(C.dim))
                    }.buttonStyle(.plain)
                    Spacer()
                    Button { player.playAll(top, source: name) } label: {
                        Image(systemName: "play.fill").font(.title2).foregroundColor(.black).frame(width: 56, height: 56)
                            .background(Circle().fill(C.green))
                    }.accessibilityLabel("Play")
                }.padding(16)
                SectionTitle("Popular")
                ForEach(Array(top.prefix(showAll ? 50 : 5).enumerated()), id: \.element.id) { i, t in
                    HStack(spacing: 0) {
                        Text("\(i + 1)").foregroundColor(C.dim).frame(width: 28)
                        TrackRow(track: t) { player.play(t, in: top, source: name) }
                    }.padding(.leading, 8)
                }
                if top.count > 5 {
                    Button(showAll ? "Show less" : "See more") { showAll.toggle() }
                        .font(.subheadline.bold()).foregroundColor(C.dim).padding(.horizontal, 16).padding(.vertical, 6)
                }
                // Spotify's artist page: albums, singles & EPs, compilations (newest first).
                ForEach([("albums", "Albums"), ("singles", "Singles and EPs"), ("compilations", "Compilations")], id: \.0) { key, heading in
                    if let group = releases[key], !group.isEmpty {
                        SectionTitle(heading)
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(alignment: .top, spacing: 14) {
                                ForEach(Array(group.enumerated()), id: \.offset) { _, a in
                                    let ref = AlbumRef(a)
                                    Card(title: ref.title, subtitle: String((a["release_date"] as? String ?? "").prefix(4)), art: ref.cover) {
                                        nav.go(.album(ref))
                                    }
                                }
                            }.padding(.horizontal, 16)
                        }
                    }
                }
                if !bio.isEmpty {
                    SectionTitle("About")
                    Text(bio).foregroundColor(C.dim).padding(.horizontal, 16)
                }
                Spacer(minLength: 24)
            }
        }
        .background(C.bg.ignoresSafeArea())
        .ignoresSafeArea(edges: .top)
        .task {
            guard top.isEmpty else { return }
            if let r = try? await Bridge.object("artist_releases", [name]) {
                releases = r.compactMapValues { $0 as? [[String: Any]] }
            }
            if let o = try? await Bridge.object("artist_top", [name, 50]) {
                top = (o["tracks"] as? [[String: Any]] ?? []).map(Track.init(dict:))
                if let a = o["artist"] as? [String: Any] { picture = a["picture_xl"] as? String ?? "" }
            }
            if let card = try? await Bridge.object("artist_card", [name]) {
                bio = card["bio"] as? String ?? ""
                fans = (card["fans"] as? NSNumber)?.intValue ?? 0
                if picture.isEmpty { picture = card["picture_url"] as? String ?? "" }
            }
        }
    }
}

struct AlbumPage: View {
    let album: AlbumRef
    @State private var tracks: [Track] = []
    var body: some View {
        SongsPage(title: album.title, subtitle: album.artist, cover: album.cover, tracks: tracks, source: album.title, kind: "Album")
            .task {
                if tracks.isEmpty { tracks = (try? await Bridge.tracks("album_tracks", [Bridge.json(album.dict)])) ?? [] }
            }
    }
}

struct GenrePage: View {
    let id: Int
    let name: String
    @EnvironmentObject var player: Player
    @EnvironmentObject var nav: Nav
    @State private var tracks: [Track] = []
    @State private var albums: [[String: Any]] = []
    @State private var loading = true

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                Text(name).font(.largeTitle.bold()).padding(16)
                if loading { ProgressView().frame(maxWidth: .infinity).padding(24) }
                if !albums.isEmpty {
                    SectionTitle("Popular albums")
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(alignment: .top, spacing: 14) {
                            ForEach(Array(albums.prefix(12).enumerated()), id: \.offset) { _, a in
                                let ref = AlbumRef(a)
                                Card(title: ref.title, subtitle: ref.artist, art: ref.cover) { nav.go(.album(ref)) }
                            }
                        }.padding(.horizontal, 16)
                    }
                }
                if !tracks.isEmpty {
                    HStack(spacing: 20) {
                        Spacer()
                        Button { player.playAll(tracks, source: name, shuffled: true) } label: {
                            Image(systemName: "shuffle").font(.title2).foregroundColor(player.shuffle ? C.green : C.dim)
                        }.accessibilityLabel("Shuffle")
                        Button { player.playAll(tracks, source: name, shuffled: false) } label: {
                            Image(systemName: "play.fill").font(.title2).foregroundColor(.black).frame(width: 56, height: 56)
                                .background(Circle().fill(C.green))
                        }.accessibilityLabel("Play")
                    }.padding(.horizontal, 16)
                    SectionTitle("Popular songs")
                    ForEach(tracks) { t in TrackRow(track: t) { player.play(t, in: tracks, source: name) } }
                }
                Spacer(minLength: 24)
            }
        }
        .background(C.bg.ignoresSafeArea())
        .task {
            guard tracks.isEmpty else { return }
            if let o = try? await Bridge.object("genre_overview", [id]) {
                tracks = (o["tracks"] as? [[String: Any]] ?? []).map(Track.init(dict:))
                albums = (o["releases"] as? [[String: Any]] ?? []) + (o["albums"] as? [[String: Any]] ?? [])
            }
            loading = false
        }
    }
}
