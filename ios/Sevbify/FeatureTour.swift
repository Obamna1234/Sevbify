import SwiftUI

/// "How to use Sevbify": the short guide shown on the first start (and from Settings → About → How to use Sevbify),
/// the same pages as Android. Swipe or tap Next; each page is one thing most people use and where to find it. The
/// pictures are drawn symbols, so they never show anyone else's music. "Don't show this again" keeps it closed.
final class Tour: ObservableObject {
    static let shared = Tour()
    @Published var open = false
    @Published var fromSettings = false

    struct Page { let symbol: String; let colour: Color; let title: String; let text: String }
    let pages: [Page] = [
        Page(symbol: "headphones", colour: Color(red: 0.12, green: 0.84, blue: 0.38), title: "Welcome to Sevbify",
             text: "Free music with no account, no ads and no tracking. Your library, playlists and downloads stay on this iPhone."),
        Page(symbol: "magnifyingglass", colour: Color(red: 0.31, green: 0.55, blue: 1), title: "Search and play",
             text: "Search finds songs, artists, albums and podcasts. Tap any song to play it in full."),
        Page(symbol: "plus.circle", colour: Color(red: 0.91, green: 0.12, blue: 0.39), title: "Save what you like",
             text: "Tap ⊕ in the player to add a song to Liked Songs, or ••• for more: add to a playlist or the queue, song radio, hide."),
        Page(symbol: "music.note.list", colour: Color(red: 1, green: 0.6, blue: 0), title: "Playlists and folders",
             text: "Your Library → + makes a playlist; ••• → Move to folder groups them. Import brings in a Spotify, Apple Music or Deezer playlist from its link."),
        Page(symbol: "arrow.down.circle", colour: Color(red: 0, green: 0.75, blue: 0.65), title: "Download for offline",
             text: "Tap ↓ on a song or playlist to keep it on this iPhone. Smart downloads (Settings) can do it for songs you play a lot."),
        Page(symbol: "mic", colour: Color(red: 0.61, green: 0.15, blue: 0.69), title: "Podcasts",
             text: "Your Library → Podcasts: follow shows and save episodes to Your Episodes. Sevbify remembers where you stopped."),
        Page(symbol: "play.rectangle", colour: Color(red: 0.25, green: 0.32, blue: 0.71), title: "Now Playing",
             text: "Tap the mini player: lyrics, Canvas loops, the queue, sleep timer. Scroll down for the artist, credits and what's next."),
        Page(symbol: "person.2", colour: Color(red: 1, green: 0.32, blue: 0.32), title: "Share and Blend",
             text: "Share a playlist as a link a friend can add or merge into theirs. Blend mixes your taste with a friend's. No server: the link is the playlist."),
        Page(symbol: "desktopcomputer", colour: Color(red: 0.38, green: 0.49, blue: 0.55), title: "Your computer",
             text: "Settings → Your computer → Pair. Send songs across, see what the computer plays and control it, on your own Wi-Fi."),
        Page(symbol: "slider.vertical.3", colour: Color(red: 0.55, green: 0.76, blue: 0.29), title: "Your sound",
             text: "Settings: equaliser, volume levelling and mono audio."),
        Page(symbol: "lock", colour: Color(red: 0.12, green: 0.84, blue: 0.38), title: "Private by design",
             text: "Nothing is sent to anyone. You can open this guide again from Settings → About."),
    ]

    @MainActor func showOnFirstStart() { if !Library.shared.settings.tourSeen { fromSettings = false; open = true } }
    func showAgain() { fromSettings = true; open = true }
}

struct FeatureTourView: View {
    @ObservedObject var tour = Tour.shared
    @State private var index = 0
    @State private var never = true

    @MainActor private func close() {
        if !tour.fromSettings && never { Library.shared.settings.tourSeen = true }
        tour.open = false
    }

    var body: some View {
        let pages = tour.pages
        VStack(alignment: .leading, spacing: 12) {
            TabView(selection: $index) {
                ForEach(pages.indices, id: \.self) { i in
                    VStack(alignment: .leading, spacing: 14) {
                        Spacer(minLength: 0)
                        ZStack {
                            RoundedRectangle(cornerRadius: 24)
                                .fill(LinearGradient(colors: [pages[i].colour, pages[i].colour.opacity(0.35), C.elevated],
                                                     startPoint: .topLeading, endPoint: .bottomTrailing))
                            Image(systemName: pages[i].symbol).font(.system(size: 84, weight: .semibold)).foregroundColor(.white)
                        }
                        .aspectRatio(1.3, contentMode: .fit)
                        Text(pages[i].title).font(.title.bold())
                        Text(pages[i].text).font(.body).foregroundColor(C.dim).fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, 4)
                    .tag(i)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            HStack(spacing: 6) {               // page dots: the current one stretches
                Spacer()
                ForEach(pages.indices, id: \.self) { i in
                    Capsule().fill(i == index ? C.green : C.dim.opacity(0.5))
                        .frame(width: i == index ? 22 : 8, height: 8)
                }
                Spacer()
            }
            .animation(.easeInOut(duration: 0.25), value: index)
            if !tour.fromSettings {
                Toggle("Don't show this again", isOn: $never).tint(C.green).font(.subheadline)
            }
            HStack {
                if index < pages.count - 1 { Button("Skip") { close() }.foregroundColor(C.text) }
                Spacer()
                if index > 0 { Button("Back") { withAnimation(.easeInOut) { index -= 1 } }.foregroundColor(C.text).padding(.trailing, 8) }
                Button(index == pages.count - 1 ? "Start listening" : "Next") {
                    if index == pages.count - 1 { close() } else { withAnimation(.easeInOut) { index += 1 } }
                }
                .padding(.horizontal, 22).padding(.vertical, 10)
                .background(C.green).foregroundColor(.black).clipShape(Capsule()).font(.body.bold())
            }
        }
        .padding(20)
        .background(C.bg.ignoresSafeArea())
        .preferredColorScheme(.dark)
        .onDisappear { if tour.open { close() } }
    }
}
