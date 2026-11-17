import SwiftUI
import AVKit

struct NowPlayingView: View {
    @ObservedObject private var canvas = CanvasLoop.shared
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @Environment(\.dismiss) var dismiss
    @State private var dragging: Double? = nil
    @State private var showQueue = false
    @State private var menu = false
    @State private var lyrics = false

    var body: some View {
        GeometryReader { geo in
            ScrollView(showsIndicators: false) {
                VStack(spacing: 0) {
                    main.frame(height: geo.size.height)
                    // Scroll down, like Spotify's: lyrics, about the artist, credits and what's next.
                    if let t = player.current, !t.isItem { NowPlayingCards(track: t, openLyrics: { lyrics = true }) }
                }
            }
        }
        .foregroundColor(.white)
        .background(
            LinearGradient(colors: [Color(red: 0.25, green: 0.2, blue: 0.25), C.bg], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea())
        .sheet(isPresented: $showQueue) { QueueView() }
        .fullScreenCover(isPresented: $lyrics) { LyricsView() }
        .sheet(isPresented: $menu) { if let t = player.current { TrackMenu(track: t).presentationDetents([.medium, .large]) } }
    }

    private var main: some View {
        let t = player.current
        return VStack(spacing: 0) {
            HStack {
                Button { dismiss() } label: { Image(systemName: "chevron.down").font(.title3).frame(width: 44, height: 44) }
                    .accessibilityLabel("Close")
                Spacer()
                VStack(spacing: 2) {
                    Text("PLAYING FROM").font(.caption2).foregroundColor(C.dim)
                    Text(player.sourceName).font(.caption.bold()).lineLimit(1)
                }
                Spacer()
                Button { menu = true } label: { Image(systemName: "ellipsis").font(.title3).frame(width: 44, height: 44) }
                    .accessibilityLabel("More").disabled(t == nil)
            }.padding(.horizontal, 8)

            Spacer(minLength: 12)
            GeometryReader { g in
                let side = min(g.size.width - 48, g.size.height)
                Group {
                    if canvas.current != nil {
                        CanvasLoopView().frame(width: side * 0.75, height: side).clipShape(RoundedRectangle(cornerRadius: 8))
                    } else {
                        Cover(url: t?.art ?? "", size: side, corner: 8)
                    }
                }
                .shadow(radius: 20)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            Spacer(minLength: 12)

            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(t?.title ?? "").font(.title2.bold()).lineLimit(1)
                    Button { if let a = t?.artist { nav.go(.artist(a)) } } label: {
                        Text(t?.artist ?? "").foregroundColor(C.dim).lineLimit(1)
                    }.buttonStyle(.plain)
                }
                Spacer()
                if let t, !t.isItem {
                    if lib.isDownloaded(t) {
                        Image(systemName: "arrow.down.circle.fill").font(.title2).foregroundColor(C.green)
                    } else {
                        Button { Downloads.shared.download([t]) } label: { Image(systemName: "arrow.down.circle").font(.title2) }
                            .accessibilityLabel("Download")
                    }
                }
            }.padding(.horizontal, 24)

            VStack(spacing: 4) {
                SpotifyScrubber(value: dragging ?? player.position, total: max(1, player.duration),
                                onDrag: { dragging = $0 },
                                onEnd: { if let d = dragging { player.seek(to: d); dragging = nil } })
                HStack {
                    Text(formatTime(Int((dragging ?? player.position) * 1000)))
                    Spacer()
                    Text(player.isPreview ? "Preview" : formatTime(Int(player.duration * 1000)))
                }.font(.caption).foregroundColor(C.dim)
            }.padding(.horizontal, 24).padding(.top, 12)

            HStack {
                Button { player.toggleShuffle() } label: {
                    Image(systemName: player.smartShuffle ? "sparkles" : "shuffle").font(.title3).foregroundColor(player.shuffle ? C.green : .white)
                }.accessibilityLabel("Shuffle")
                Spacer()
                Button { player.previous() } label: { Image(systemName: "backward.end.fill").font(.title) }.accessibilityLabel("Previous")
                Spacer()
                Button { player.toggle() } label: {
                    ZStack {
                        Circle().fill(Color.white).frame(width: 68, height: 68)
                        if player.loading { ProgressView().tint(.black) }
                        else { Image(systemName: player.isPlaying ? "pause.fill" : "play.fill").font(.title).foregroundColor(.black) }
                    }
                }.accessibilityLabel(player.isPlaying ? "Pause" : "Play")
                Spacer()
                Button { player.next() } label: { Image(systemName: "forward.end.fill").font(.title) }.accessibilityLabel("Next")
                Spacer()
                Button { player.cycleRepeat() } label: {
                    Image(systemName: player.repeatMode == "one" ? "repeat.1" : "repeat").font(.title3)
                        .foregroundColor(player.repeatMode == "off" ? .white : C.green)
                }.accessibilityLabel("Repeat")
            }.padding(.horizontal, 24).padding(.top, 8)

            HStack {
                // Spotify's row: devices on the left; share and queue on the right (song radio is in the ••• menu).
                RoutePicker().frame(width: 44, height: 44).accessibilityLabel("Connect to a device")
                Spacer()
                if let t, !t.isItem {
                    Button { lyrics = true } label: { Image(systemName: "quote.bubble") }
                        .accessibilityLabel("Lyrics")
                        .padding(.trailing, 20)
                    Button { Share.song(t) } label: { Image(systemName: "square.and.arrow.up") }
                        .accessibilityLabel("Share")
                        .padding(.trailing, 20)
                }
                Button { showQueue = true } label: { Image(systemName: "list.bullet") }.accessibilityLabel("Queue")
            }.font(.title3).padding(.horizontal, 24).padding(.vertical, 16)
        }
    }
}


/// AirPlay / Bluetooth speakers and headphones (Apple's own picker, like Spotify's Connect button).
/// Spotify's progress bar: a thin 4 pt line (white played part on a grey track) with a small white dot, a bit
/// bigger while you drag. The whole row height is touchable, so it's easy to grab.
struct SpotifyScrubber: View {
    let value: Double
    let total: Double
    let onDrag: (Double) -> Void
    let onEnd: () -> Void
    @State private var active = false

    var body: some View {
        GeometryReader { g in
            let w = max(1, g.size.width)
            let frac = min(1, max(0, value / total))
            ZStack(alignment: .leading) {
                Capsule().fill(Color.white.opacity(0.3)).frame(height: 4)
                Capsule().fill(Color.white).frame(width: w * frac, height: 4)
                Circle().fill(Color.white).frame(width: active ? 16 : 12, height: active ? 16 : 12)
                    .offset(x: w * frac - (active ? 8 : 6))
            }
            .frame(height: 24)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { v in active = true; onDrag(min(1, max(0, v.location.x / w)) * total) }
                .onEnded { _ in active = false; onEnd() })
        }
        .frame(height: 24)
        .animation(.easeOut(duration: 0.12), value: active)
        .accessibilityElement()
        .accessibilityLabel("Song position")
        .accessibilityValue(formatTime(Int(value * 1000)))
        .accessibilityAdjustableAction { dir in
            let step = 10.0
            onDrag(min(total, max(0, value + (dir == .increment ? step : -step)))); onEnd()
        }
    }
}

struct RoutePicker: UIViewRepresentable {
    func makeUIView(context: Context) -> AVRoutePickerView {
        let v = AVRoutePickerView()
        v.tintColor = .white
        v.activeTintColor = UIColor(C.green)
        v.prioritizesVideoDevices = false
        return v
    }
    func updateUIView(_ uiView: AVRoutePickerView, context: Context) {}
}

struct QueueView: View {
    @EnvironmentObject var player: Player
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationStack {
            List {
                if let t = player.current {
                    Section("Now playing") { QueueRow(track: t, playing: true) }
                }
                if !player.userQueue.isEmpty {
                    Section("Next in queue") {
                        ForEach(player.userQueue) { t in QueueRow(track: t).onTapGesture { player.jump(to: t) } }
                            .onDelete { player.userQueue.remove(atOffsets: $0) }
                    }
                }
                Section("Next from: \(player.sourceName)") {
                    ForEach(player.upcoming.prefix(100)) { t in QueueRow(track: t).onTapGesture { player.jump(to: t) } }
                }
            }
            .listStyle(.plain).scrollContentBackground(.hidden).background(C.elevated)
            .navigationTitle("Queue").navigationBarTitleDisplayMode(.inline)
            .toolbar { Button("Done") { dismiss() } }
        }
    }
}

struct QueueRow: View {
    let track: Track
    var playing = false
    var body: some View {
        HStack {
            Cover(url: track.art, size: 40)
            VStack(alignment: .leading) {
                Text(track.title).foregroundColor(playing ? C.green : C.text).lineLimit(1)
                Text(track.artist).font(.caption).foregroundColor(C.dim).lineLimit(1)
            }
        }.listRowBackground(C.elevated).contentShape(Rectangle())
    }
}

/// Full-screen lyrics, like Spotify's (and the PC's and Android's): from LRCLIB, the open lyrics library. Synced
/// lyrics follow the song and a tap on a line jumps there.
struct LyricsView: View {
    @EnvironmentObject var player: Player
    @Environment(\.dismiss) var dismiss
    @State private var lines: [(ms: Int, text: String)] = []
    @State private var plain: [String] = []
    @State private var state = "Loading lyrics…"
    @State private var loadedFor = ""

    private var current: Int {
        let ms = Int(player.position * 1000)
        return (lines.lastIndex { $0.ms <= ms + 300 }) ?? -1
    }

    var body: some View {
        let t = player.current
        VStack(spacing: 0) {
            HStack {
                Button { dismiss() } label: { Image(systemName: "chevron.down").font(.title3).frame(width: 44, height: 44) }
                    .accessibilityLabel("Close")
                Spacer()
                VStack(spacing: 2) {
                    Text(t?.title ?? "").font(.subheadline.bold()).lineLimit(1)
                    Text(t?.artist ?? "").font(.caption).foregroundColor(.white.opacity(0.7)).lineLimit(1)
                }
                Spacer()
                Color.clear.frame(width: 44, height: 44)
            }.padding(.horizontal, 8)
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        if !lines.isEmpty {
                            ForEach(Array(lines.enumerated()), id: \.offset) { i, l in
                                Text(l.text.isEmpty ? "♪" : l.text)
                                    .font(.system(size: 26, weight: .bold))
                                    .foregroundColor(i == current ? .white : (i < current ? .white.opacity(0.6) : .black.opacity(0.45)))
                                    .id(i)
                                    .onTapGesture { player.seek(to: Double(l.ms) / 1000) }
                            }
                        } else if !plain.isEmpty {
                            ForEach(Array(plain.enumerated()), id: \.offset) { _, l in
                                Text(l.isEmpty ? " " : l).font(.system(size: 24, weight: .bold))
                            }
                        } else {
                            Text(state).font(.title3.bold()).foregroundColor(.white.opacity(0.8)).padding(.top, 40)
                        }
                        Text("Lyrics from LRCLIB").font(.caption).foregroundColor(.white.opacity(0.6)).padding(.top, 24)
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 24).padding(.vertical, 16)
                }
                .onChange(of: current) { i in
                    if i > 1 { withAnimation(.easeInOut(duration: 0.4)) { proxy.scrollTo(i - 1, anchor: .top) } }
                }
            }
            HStack {
                Text(formatTime(Int(player.position * 1000))).font(.caption)
                Spacer()
                Button { player.toggle() } label: {
                    ZStack {
                        Circle().fill(Color.white).frame(width: 60, height: 60)
                        Image(systemName: player.isPlaying ? "pause.fill" : "play.fill").font(.title2).foregroundColor(.black)
                    }
                }.accessibilityLabel(player.isPlaying ? "Pause" : "Play")
                Spacer()
                Text(formatTime(Int(player.duration * 1000))).font(.caption)
            }.padding(.horizontal, 24).padding(.vertical, 16)
        }
        .foregroundColor(.white)
        .background(Color(red: 0.42, green: 0.32, blue: 0.36).ignoresSafeArea())
        .task(id: t?.matchKey ?? "") { await load(t) }
    }

    private func load(_ t: Track?) async {
        guard let t, t.matchKey != loadedFor else { return }
        loadedFor = t.matchKey
        lines = []; plain = []; state = "Loading lyrics…"
        guard let o = try? await Bridge.object("lyrics", [t.artist, t.title, t.album, t.durationMs]), !o.isEmpty else {
            state = "No lyrics found for this song."; return
        }
        lines = (o["lines"] as? [[Any]] ?? []).compactMap { r in
            guard r.count >= 2, let ms = (r[0] as? NSNumber)?.intValue else { return nil }
            return (ms, String(describing: r[1]))
        }
        if lines.isEmpty { plain = (o["plain"] as? String ?? "").components(separatedBy: "\n") }
        if lines.isEmpty && plain.allSatisfy({ $0.trimmingCharacters(in: .whitespaces).isEmpty }) {
            plain = []; state = "No lyrics found for this song."
        }
    }
}

/// The cards under Now Playing (like Spotify's): Lyrics, About the artist, Credits and Next in queue.
struct NowPlayingCards: View {
    let track: Track
    let openLyrics: () -> Void
    @EnvironmentObject var player: Player
    @EnvironmentObject var nav: Nav
    @State private var lyricLines: [String] = []
    @State private var artist: [String: Any] = [:]
    @State private var credits: [[String: Any]] = []

    var body: some View {
        VStack(spacing: 12) {
            if !lyricLines.isEmpty {
                card("Lyrics", colour: Color(red: 0.42, green: 0.32, blue: 0.36)) {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(lyricLines.prefix(6).enumerated()), id: \.offset) { _, l in Text(l).font(.title3.bold()) }
                        Button("Show lyrics") { openLyrics() }.buttonStyle(.bordered).tint(.white).padding(.top, 6)
                    }
                }
            }
            if !artist.isEmpty {
                card("About the artist") {
                    VStack(alignment: .leading, spacing: 8) {
                        if let p = artist["picture_url"] as? String, !p.isEmpty {
                            Cover(url: p, size: 300, corner: 8).frame(maxWidth: .infinity)
                        }
                        Text(artist["name"] as? String ?? track.artist).font(.headline)
                        if let fans = artist["fans"] as? Int, fans > 0 {
                            Text("\(fans.formatted()) fans on Deezer").font(.caption).foregroundColor(C.dim)
                        }
                        if let bio = artist["bio"] as? String, !bio.isEmpty { Text(bio).font(.subheadline).lineLimit(5) }
                        Button("Open artist page") { nav.go(.artist(track.artist)) }.buttonStyle(.bordered).tint(.white)
                    }
                }
            }
            if !credits.isEmpty {
                card("Credits") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(credits.prefix(6).enumerated()), id: \.offset) { _, r in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(r["name"] as? String ?? "")
                                Text((r["roles"] as? [String] ?? []).joined(separator: ", ")).font(.caption).foregroundColor(C.dim)
                            }
                        }
                    }
                }
            }
            let next = Array((player.userQueue + player.upcoming).prefix(3))
            if !next.isEmpty {
                card("Next in queue") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(next) { t in
                            HStack {
                                Cover(url: t.art, size: 44)
                                VStack(alignment: .leading) {
                                    Text(t.title).lineLimit(1)
                                    Text(t.artist).font(.caption).foregroundColor(C.dim).lineLimit(1)
                                }
                                Spacer()
                            }
                            .contentShape(Rectangle())
                            .onTapGesture { player.jump(to: t) }
                        }
                    }
                }
            }
        }
        .padding(.horizontal, 16).padding(.bottom, 32)
        .task(id: track.matchKey) { await load() }
    }

    private func card<Content: View>(_ title: String, colour: Color = C.card, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.headline)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 10).fill(colour))
    }

    private func load() async {
        lyricLines = []; artist = [:]; credits = []
        guard Library.shared.settings.online else { return }
        if let o = try? await Bridge.object("lyrics", [track.artist, track.title, track.album, track.durationMs]), !o.isEmpty {
            let synced = (o["lines"] as? [[Any]] ?? []).compactMap { $0.count >= 2 ? String(describing: $0[1]) : nil }
            let lines = synced.isEmpty ? (o["plain"] as? String ?? "").components(separatedBy: "\n") : synced
            lyricLines = lines.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        }
        if !track.artist.isEmpty, track.artist != "Unknown Artist" {
            let card = (try? await Bridge.object("artist_card", [track.artist])) ?? [:]
            artist = card.count > 1 ? card : [:]
            credits = (try? await Bridge.list("credits", [track.artist, track.title])) ?? []
        }
    }
}
