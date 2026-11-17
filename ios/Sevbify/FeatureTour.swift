import SwiftUI
import UIKit

/// The feature tour: a few pages with a screenshot each (Tour/*.jpg, made by tools/tour_images.py from the iPhone
/// screenshots, playing openly licensed music). Opens once after the first-start notice; "Don't show this again"
/// keeps it closed; Settings → About → Feature tour opens it again.
final class Tour: ObservableObject {
    static let shared = Tour()
    @Published var open = false
    @Published var fromSettings = false

    struct Page { let picture: String; let title: String; let text: String }
    /// The pages whose picture is in the app (all of them if none are).
    var pages: [Page] {
        let have = all.filter { Bundle.main.url(forResource: $0.picture, withExtension: nil, subdirectory: "Tour") != nil }
        return have.isEmpty ? all : have
    }
    private let all: [Page] = [
        Page(picture: "home.jpg", title: "Welcome to Sevbify",
             text: "Free music with no account, no ads and no tracking. Your library, playlists and downloads stay on this iPhone."),
        Page(picture: "search.jpg", title: "Search everywhere at once",
             text: "One search looks through YouTube, Bandcamp, Deezer and your own music. Play any result straight away, full length."),
        Page(picture: "library.jpg", title: "Bring your Spotify playlists",
             text: "Your Library → Import: paste a Spotify, Apple Music or Deezer link. More than 100 songs? In Spotify select all songs, copy, and paste them in the songs box. Your Spotify account is never signed in to."),
        Page(picture: "now_playing.jpg", title: "Now playing",
             text: "Lyrics that follow the song, the queue, sharing, and ••• for more: download, radio, Support the artist."),
        Page(picture: "pair.jpg", title: "Send music to your computer",
             text: "Settings → Your computer → Pair, and scan the code Sevbify shows on your computer. Songs go straight to it over your own Wi-Fi, encrypted."),
        Page(picture: "support.jpg", title: "Support the artist",
             text: "••• → Support the artist to buy their music straight from them: their own Bandcamp page or official shop. You can open this tour again from Settings → About."),
    ]

    func showOnFirstStart() { if !Library.shared.settings.tourSeen { fromSettings = false; open = true } }
    func showAgain() { fromSettings = true; open = true }
}

struct FeatureTourView: View {
    @ObservedObject var tour = Tour.shared
    @State private var index = 0
    @State private var never = true

    private func close() {
        if !tour.fromSettings && never { Library.shared.settings.tourSeen = true }
        tour.open = false
    }

    private func picture(_ name: String) -> UIImage? {
        guard let url = Bundle.main.url(forResource: name, withExtension: nil, subdirectory: "Tour") else { return nil }
        return UIImage(contentsOfFile: url.path)
    }

    var body: some View {
        let pages = tour.pages
        VStack(alignment: .leading, spacing: 10) {
            TabView(selection: $index) {
                ForEach(pages.indices, id: \.self) { i in
                    ZStack {
                        RoundedRectangle(cornerRadius: 12).fill(C.elevated)
                        if let img = picture(pages[i].picture) {
                            Image(uiImage: img).resizable().scaledToFit().cornerRadius(12)
                        }
                    }.tag(i)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
            Text(pages[index].title).font(.title2.bold())
            Text(pages[index].text).font(.subheadline).foregroundColor(C.dim)
                .frame(minHeight: 72, alignment: .topLeading)
            if !tour.fromSettings {
                Toggle("Don't show this again", isOn: $never).tint(C.green).font(.subheadline)
            }
            HStack {
                if index < pages.count - 1 { Button("Skip") { close() }.foregroundColor(C.text) }
                Spacer()
                if index > 0 { Button("Back") { withAnimation { index -= 1 } }.foregroundColor(C.text).padding(.trailing, 8) }
                Button(index == pages.count - 1 ? "Done" : "Next") {
                    if index == pages.count - 1 { close() } else { withAnimation { index += 1 } }
                }
                .padding(.horizontal, 22).padding(.vertical, 10)
                .background(C.green).foregroundColor(.black).clipShape(Capsule()).font(.body.bold())
            }
        }
        .padding(20)
        .background(C.bg.ignoresSafeArea())
        .preferredColorScheme(.dark)
        .interactiveDismissDisabled(false)
        .onDisappear { if tour.open { close() } }
    }
}
