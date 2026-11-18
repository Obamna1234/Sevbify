import SwiftUI
import AVFoundation

/// Song menu → Preview (30 s), like a small Spotify player over the app: whatever was playing pauses, the clip plays
/// on its own AVPlayer, and the slider can be dragged anywhere in the 30 seconds. Restart goes back to 0:00, Add to
/// queue keeps the song for later, ⊕ saves it. "Play full song" plays the whole song now (the one you were playing
/// stays as the previous song); Close carries on with your song where it paused. It's the only place a clip plays.
struct PreviewView: View {
    let track: Track
    var onFull: () -> Void = {}
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @Environment(\.dismiss) var dismiss
    @State private var clip = AVPlayer()
    @State private var missing = false
    @State private var playing = false
    @State private var pos: Double = 0
    @State private var len: Double = 30
    @State private var dragging = false
    @State private var wasPlaying = false
    @State private var goingFull = false
    @State private var savedIn: Track?
    private let tick = Timer.publish(every: 0.1, on: .main, in: .common).autoconnect()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    // Plainly a preview: a green badge, a 0:30 tag on the cover and "0:30" at the end of the slider.
                    Text("30-SECOND PREVIEW").font(.caption.bold()).foregroundColor(.black)
                        .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(C.green))
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.headline).frame(width: 34, height: 34)
                            .background(Circle().fill(Color.white.opacity(0.14)))
                    }.buttonStyle(.plain).accessibilityLabel("Close")
                }
                ZStack(alignment: .bottomTrailing) {
                    GeometryReader { g in Cover(url: track.art, size: g.size.width, corner: 8) }.aspectRatio(1, contentMode: .fit)
                    Text("0:30").font(.caption.bold()).padding(.horizontal, 6).padding(.vertical, 2)
                        .background(RoundedRectangle(cornerRadius: 4).fill(Color.black.opacity(0.8))).padding(8)
                }
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(track.title).font(.title2.bold()).lineLimit(1)
                        Text(track.artist).foregroundColor(C.dim).lineLimit(1)
                    }
                    Spacer()
                    let saved = SaveButton.isSaved(track)
                    Button { if SaveButton.tap(track) { savedIn = track } } label: {
                        Image(systemName: saved ? "checkmark.circle.fill" : "plus.circle").font(.title2)
                            .foregroundColor(saved ? C.green : C.dim)
                    }.buttonStyle(.plain).accessibilityLabel(saved ? "Saved in…" : "Add to Liked Songs")
                }
                if missing {
                    Text("There's no preview for this song, but you can play the full song.").foregroundColor(C.dim)
                } else {
                    VStack(spacing: 2) {
                        SpotifyScrubber(value: pos, total: max(len, 1),
                                        onDrag: { dragging = true; pos = $0 },
                                        onEnd: {
                                            clip.seek(to: CMTime(seconds: pos, preferredTimescale: 600)) { _ in dragging = false }
                                            clip.play()
                                        })
                        HStack { Text(clock(pos)); Spacer(); Text(clock(len)) }.font(.caption).foregroundColor(C.dim).monospacedDigit()
                    }
                    HStack {
                        side("arrow.counterclockwise", "Restart") { clip.seek(to: .zero); clip.play() }
                        Spacer()
                        Button {
                            if playing { clip.pause() } else { if pos >= len - 0.3 { clip.seek(to: .zero) }; clip.play() }
                        } label: {
                            ZStack {
                                Circle().fill(Color.white).frame(width: 62, height: 62)
                                Image(systemName: playing ? "pause.fill" : "play.fill").font(.title).foregroundColor(.black)
                            }
                        }.buttonStyle(.plain).accessibilityLabel(playing ? "Pause" : "Play")
                        Spacer()
                        side("text.append", "Add to queue") { player.addToQueue(track) }
                    }.padding(.horizontal, 12)
                }
                HStack(spacing: 10) {
                    Button { goingFull = true; dismiss(); playFull() } label: {
                        Label("Play full song", systemImage: "play.fill").font(.headline).foregroundColor(.black)
                            .frame(maxWidth: .infinity).padding(.vertical, 13).background(Capsule().fill(C.green))
                    }.buttonStyle(.plain)
                    Button { dismiss() } label: {
                        Text("Close").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 13)
                            .overlay(Capsule().stroke(Color.gray, lineWidth: 1))
                    }.buttonStyle(.plain)
                }
                if wasPlaying {
                    Text("Close and your song carries on where it was").font(.caption).foregroundColor(C.dim)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(20)
        }
        .background(LinearGradient(colors: [Color(red: 0.23, green: 0.31, blue: 0.42), Color(red: 0.12, green: 0.15, blue: 0.2), C.bg],
                                   startPoint: .top, endPoint: .bottom).ignoresSafeArea())
        .foregroundColor(.white)
        .presentationDetents([.large])
        .sheet(item: $savedIn) { SavedInView(track: $0).environmentObject(lib) }
        .task { await start() }
        .onReceive(tick) { _ in
            playing = clip.timeControlStatus == .playing
            if let d = clip.currentItem?.duration.seconds, d.isFinite, d > 0 { len = d }
            if !dragging { pos = clip.currentTime().seconds.isFinite ? clip.currentTime().seconds : 0 }
        }
        .onDisappear {
            clip.pause(); clip.replaceCurrentItem(with: nil)
            if wasPlaying && !goingFull && !player.isPlaying { player.toggle() }      // carry on where it was
        }
    }

    private func side(_ icon: String, _ label: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) { Image(systemName: icon).font(.title2); Text(label).font(.caption2).foregroundColor(C.dim) }
                .frame(width: 84)
        }.buttonStyle(.plain).accessibilityLabel(label)
    }

    private func playFull() {
        if player.current == nil { player.play(track, in: [track], source: "Preview") }
        else { player.playNext(track); player.next() }
        onFull()
    }

    private func start() async {
        wasPlaying = player.isPlaying
        player.pause()
        var link = track.previewUrl
        if link.isEmpty { link = (try? await Bridge.call("preview_url", [track.artist, track.title])) as? String ?? "" }
        guard !link.isEmpty, let url = URL(string: link) else { missing = true; return }
        clip.replaceCurrentItem(with: AVPlayerItem(url: url))
        clip.play()
    }

    private func clock(_ s: Double) -> String {
        let n = Int(max(0, s.rounded())); return "\(n / 60):" + String(format: "%02d", n % 60)
    }
}
