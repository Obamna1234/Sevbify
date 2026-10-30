import SwiftUI

struct HomeView: View {
    @EnvironmentObject var lib: Library
    @EnvironmentObject var player: Player
    @EnvironmentObject var nav: Nav
    @State private var genres: [[String: Any]] = []

    private var greeting: String {
        let h = Calendar.current.component(.hour, from: Date())
        return h < 12 ? "Good morning" : (h < 18 ? "Good afternoon" : "Good evening")
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Image("Logo").resizable().frame(width: 32, height: 32).clipShape(Circle())
                    Text(greeting).font(.title.bold())
                    Spacer()
                    Button { nav.go(.settings) } label: { Image(systemName: "gearshape").font(.title3) }
                        .accessibilityLabel("Settings")
                }.padding(.horizontal, 16).padding(.top, 8)

                // Quick tiles, like Spotify's: Your Songs and your recent playlists.
                let tiles = Array(lib.playlists.sorted { $0.lastPlayed > $1.lastPlayed }.prefix(5))
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)], spacing: 8) {
                    Tile(title: "Your Songs", art: AnyView(LinearGradient(colors: [Color(red: 0.27, green: 0.04, blue: 0.96), Color(red: 0.77, green: 0.94, blue: 0.85)], startPoint: .topLeading, endPoint: .bottomTrailing).overlay(Image(systemName: "music.note").foregroundColor(.white)))) {
                        nav.go(.yourSongs)
                    }
                    ForEach(tiles) { pl in
                        Tile(title: pl.name, art: AnyView(PlaylistCover(playlist: pl, size: 56))) { nav.go(.playlist(pl.id)) }
                    }
                }.padding(.horizontal, 16).padding(.top, 16)

                if !lib.recent.isEmpty {
                    SectionTitle("Recently played")
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(alignment: .top, spacing: 14) {
                            ForEach(lib.recent.prefix(15)) { t in
                                Card(title: t.title, subtitle: t.artist, art: t.art) {
                                    player.play(t, in: Array(lib.recent.prefix(15)), source: "Recently played")
                                }
                            }
                        }.padding(.horizontal, 16)
                    }
                }

                if !lib.playlists.isEmpty {
                    SectionTitle("Your playlists")
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(alignment: .top, spacing: 14) {
                            ForEach(lib.playlists) { pl in
                                Button { nav.go(.playlist(pl.id)) } label: {
                                    VStack(alignment: .leading, spacing: 6) {
                                        PlaylistCover(playlist: pl, size: 140)
                                        Text(pl.name).font(.subheadline.bold()).lineLimit(1)
                                        Text("Playlist • \(pl.tracks.count) songs").font(.caption).foregroundColor(C.dim)
                                    }.frame(width: 140, alignment: .leading)
                                }.buttonStyle(.plain)
                            }
                        }.padding(.horizontal, 16)
                    }
                }

                if lib.settings.online && !genres.isEmpty {
                    SectionTitle("Browse")
                    GenreGrid(genres: genres)
                }
                Spacer(minLength: 24)
            }
        }
        .background(C.bg.ignoresSafeArea())
        .navigationBarHidden(true)
        .task {
            if genres.isEmpty && lib.settings.online { genres = (try? await Bridge.list("genres")) ?? [] }
        }
    }
}

struct Tile: View {
    let title: String
    let art: AnyView
    var action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                art.frame(width: 56, height: 56).clipped()
                Text(title).font(.subheadline.bold()).lineLimit(2).multilineTextAlignment(.leading)
                Spacer(minLength: 0)
            }
            .background(C.card).cornerRadius(4)
        }.buttonStyle(.plain)
    }
}

struct Card: View {
    let title: String
    let subtitle: String
    let art: String
    var round = false
    var action: () -> Void
    var body: some View {
        Button(action: action) {
            VStack(alignment: round ? .center : .leading, spacing: 6) {
                Cover(url: art, size: 140, corner: round ? 70 : 4)
                Text(title).font(.subheadline.bold()).lineLimit(1)
                if !subtitle.isEmpty { Text(subtitle).font(.caption).foregroundColor(C.dim).lineLimit(1) }
            }.frame(width: 140, alignment: round ? .center : .leading)
        }.buttonStyle(.plain)
    }
}

struct GenreGrid: View {
    let genres: [[String: Any]]
    @EnvironmentObject var nav: Nav
    private let colours: [Color] = [.pink, .orange, .purple, .blue, .teal, .red, .indigo, .green, .brown, .mint]
    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
            ForEach(Array(genres.enumerated()), id: \.offset) { i, g in
                let name = g["name"] as? String ?? ""
                Button { nav.go(.genre((g["id"] as? NSNumber)?.intValue ?? 0, name)) } label: {
                    ZStack(alignment: .topLeading) {
                        colours[i % colours.count].opacity(0.85)
                        Text(name).font(.headline).padding(10)
                    }.frame(height: 96).cornerRadius(6)
                }.buttonStyle(.plain)
            }
        }.padding(.horizontal, 16)
    }
}
