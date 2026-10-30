import SwiftUI

@main
struct SevbifyApp: App {
    @StateObject private var lib = Library.shared
    @StateObject private var player = Player.shared
    @StateObject private var downloads = Downloads.shared
    @StateObject private var nav = Nav()

    init() {
        // Python starts in the background (it takes a moment the first time).
        Task { @MainActor in
            let s = Library.shared.settings
            let version = Bundle.main.object(forInfoDictionaryKey: "SevbifyVersion") as? String ?? ""
            let data = Library.support.path, cache = Library.support.appendingPathComponent("cache").path
            let ok = await Task.detached(priority: .userInitiated) { () -> Bool in
                guard Bridge.start() else { return false }
                return (try? Bridge.callSync("setup", [data, cache, s.online, s.lastfmKey, version])) != nil
            }.value
            Bridge.markReady()
            if ok {
                _ = try? await Bridge.call("set_source", [s.source])
                await Library.shared.scan()
            }
            Smoke.runIfAsked()
            if ok && !Smoke.args.contains("-SEVSmoke") { await AppUpdates.shared.check() }
        }
        let tab = UITabBarAppearance()
        tab.configureWithOpaqueBackground()
        tab.backgroundColor = UIColor(white: 0.04, alpha: 0.97)
        UITabBar.appearance().standardAppearance = tab
        UITabBar.appearance().scrollEdgeAppearance = tab
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(lib).environmentObject(player).environmentObject(downloads).environmentObject(nav)
                .preferredColorScheme(.dark)
                .tint(C.green)
                .modifier(UpdateAlert())
                .modifier(ImportReviewSheet())
        }
    }
}

/// Which tab is open and the pages opened in each (like Spotify: Home, Search, Your Library).
@MainActor
final class Nav: ObservableObject {
    enum Tab: Hashable { case home, search, library }
    @Published var tab: Tab = .home
    @Published var home = NavigationPath()
    @Published var search = NavigationPath()
    @Published var library = NavigationPath()
    @Published var nowPlaying = false
    static weak var current: Nav?
    init() { Nav.current = self }

    func go(_ r: Route) {
        nowPlaying = false
        switch tab {
        case .home: home.append(r)
        case .search: search.append(r)
        case .library: library.append(r)
        }
    }
}

struct RootView: View {
    @EnvironmentObject var nav: Nav
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library

    var body: some View {
        TabView(selection: $nav.tab) {
            NavigationStack(path: $nav.home) { HomeView().destinations() }
                .withMiniPlayer()
                .tabItem { Label("Home", systemImage: "house.fill") }.tag(Nav.Tab.home)
            NavigationStack(path: $nav.search) { SearchView().destinations() }
                .withMiniPlayer()
                .tabItem { Label("Search", systemImage: "magnifyingglass") }.tag(Nav.Tab.search)
            NavigationStack(path: $nav.library) { LibraryView().destinations() }
                .withMiniPlayer()
                .tabItem { Label("Your Library", systemImage: "books.vertical.fill") }.tag(Nav.Tab.library)
        }
        .fullScreenCover(isPresented: $nav.nowPlaying) { NowPlayingView() }
        .overlay(alignment: .top) { Toast() }
        .sheet(isPresented: Binding(get: { !lib.settings.noticeAccepted }, set: { _ in })) { FirstRunNotice() }
    }
}

extension View {
    func withMiniPlayer() -> some View {
        safeAreaInset(edge: .bottom, spacing: 0) { MiniPlayer() }
    }

    func destinations() -> some View {
        navigationDestination(for: Route.self) { r in
            Group {
                switch r {
                case .playlist(let id): PlaylistPage(id: id)
                case .yourSongs: YourSongsPage()
                case .artist(let name): ArtistPage(name: name)
                case .album(let a): AlbumPage(album: a)
                case .genre(let id, let name): GenrePage(id: id, name: name)
                case .songs(let title, let tracks): SongsPage(title: title, subtitle: "", cover: tracks.first?.art ?? "", tracks: tracks, source: title)
                case .radio(let title, let tracks): SongsPage(title: title, subtitle: radioSubtitle(tracks), cover: tracks.first?.art ?? "",
                                                              tracks: tracks, source: title, kind: "Radio")
                case .settings: SettingsView()
                case .importLink: ImportView()
                case .downloads: DownloadsPage()
                }
            }
            .background(C.bg.ignoresSafeArea())
        }
        .background(C.bg.ignoresSafeArea())
    }
}

/// The bar above the tabs: what's playing, play/pause; tap it for Now Playing.
struct MiniPlayer: View {
    @EnvironmentObject var player: Player
    @EnvironmentObject var nav: Nav
    var body: some View {
        if let t = player.current {
            VStack(spacing: 0) {
                HStack(spacing: 10) {
                    Cover(url: t.art, size: 40)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(t.title).font(.subheadline.weight(.semibold)).lineLimit(1)
                        Text(player.isPreview ? "Preview • \(t.artist)" : t.artist).font(.caption).foregroundColor(C.dim).lineLimit(1)
                    }
                    Spacer()
                    if player.loading { ProgressView().frame(width: 40, height: 40) }
                    else {
                        Button { player.toggle() } label: {
                            Image(systemName: player.isPlaying ? "pause.fill" : "play.fill").font(.title3).frame(width: 40, height: 40)
                        }.buttonStyle(.plain).accessibilityLabel(player.isPlaying ? "Pause" : "Play")
                    }
                }
                .padding(.horizontal, 8).padding(.vertical, 6)
                ProgressView(value: player.duration > 0 ? min(1, player.position / player.duration) : 0)
                    .tint(.white).scaleEffect(x: 1, y: 0.5).padding(.horizontal, 8)
            }
            .background(RoundedRectangle(cornerRadius: 8).fill(Color(red: 0.2, green: 0.17, blue: 0.2)))
            .padding(.horizontal, 8).padding(.bottom, 4)
            .contentShape(Rectangle())
            .onTapGesture { nav.nowPlaying = true }
        }
    }
}

/// Short messages ("Added to queue", errors) that fade away.
struct Toast: View {
    @EnvironmentObject var player: Player
    @State private var shown = ""
    var body: some View {
        Group {
            if !shown.isEmpty {
                Text(shown).font(.subheadline).padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Capsule().fill(Color.white)).foregroundColor(.black).padding(.top, 8)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .onChange(of: player.status) { s in
            guard !s.isEmpty else { return }
            withAnimation { shown = s }
            let now = s
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                if shown == now { withAnimation { shown = "" }; if player.status == now { player.status = "" } }
            }
        }
    }
}

/// Shown once: what Sevbify does online, and that nothing about you is collected.
struct FirstRunNotice: View {
    @EnvironmentObject var lib: Library
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Image("Logo").resizable().scaledToFit().frame(width: 72, height: 72).cornerRadius(16)
                Text("Welcome to Sevbify").font(.largeTitle.bold())
                Text("Your music, Spotify-style. No account, no ads, no tracking, nothing sold.")
                Text("Online, Sevbify only contacts what each feature needs: Deezer (search, radio, genres), Wikipedia (artist info), DuckDuckGo (only a finished search whose results look wrong, for “Did you mean”), Apple (podcast directory), the podcasts' own feeds, the Internet Archive (audiobooks), Bandcamp and YouTube (full songs and downloads), Spotify, Apple Music or Deezer only when you import a link, LRCLIB for lyrics, song.link when you share, and GitHub for updates. You can turn online features off in Settings.")
                    .foregroundColor(C.dim)
                Text("Your own songs: put them in Files ▸ On My iPhone ▸ Sevbify, or add a folder in Your Library. Sevbify only looks in folders you choose.")
                    .foregroundColor(C.dim)
                Text("Only download music you have the right to download.").foregroundColor(C.dim)
                Button { lib.settings.noticeAccepted = true } label: {
                    Text("Got it").bold().frame(maxWidth: .infinity).padding().background(C.green).foregroundColor(.black).cornerRadius(24)
                }.padding(.top, 8)
            }.padding(24)
        }
        .background(C.bg.ignoresSafeArea())
        .interactiveDismissDisabled()
    }
}


/// Like Spotify: "With Turboslash, Isidor, Nightstop and more"
func radioSubtitle(_ tracks: [Track]) -> String {
    let seed = tracks.first?.artist ?? ""
    var seen: [String] = []
    for t in tracks where !t.artist.isEmpty && t.artist != seed && !seen.contains(t.artist) {
        seen.append(t.artist)
        if seen.count == 3 { break }
    }
    return seen.isEmpty ? "" : "With \(seen.joined(separator: ", ")) and more"
}
