import SwiftUI
import AVFoundation

/// Song menu → Preview: the 30-second clip in a small sheet with a seek bar. It's the only place a clip plays;
/// everything else streams the full song. Uses its own AVPlayer, so the main song is only paused.
struct PreviewView: View {
    let track: Track
    @EnvironmentObject var player: Player
    @State private var clip = AVPlayer()
    @State private var missing = false
    @State private var playing = false
    @State private var pos: Double = 0
    @State private var len: Double = 30
    @State private var dragging = false
    private let tick = Timer.publish(every: 0.2, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(track.title).font(.headline).lineLimit(2)
            Text(missing ? "No preview for this song" : "\(track.artist) · 30-second preview")
                .font(.subheadline).foregroundColor(C.dim).lineLimit(1)
            if !missing {
                HStack(spacing: 12) {
                    Button {
                        if playing { clip.pause() } else {
                            if pos >= len - 0.3 { clip.seek(to: .zero) }
                            clip.play()
                        }
                    } label: {
                        Image(systemName: playing ? "pause.circle.fill" : "play.circle.fill")
                            .font(.system(size: 36)).foregroundColor(C.green)
                    }.buttonStyle(.plain)
                    Slider(value: $pos, in: 0...max(len, 1), onEditingChanged: { editing in
                        dragging = editing
                        if !editing { clip.seek(to: CMTime(seconds: pos, preferredTimescale: 600)); clip.play() }
                    }).tint(C.green)
                    Text(clock(pos)).font(.caption).foregroundColor(C.dim).monospacedDigit()
                }
            }
            Spacer(minLength: 0)
        }
        .padding(20)
        .background(C.elevated.ignoresSafeArea())
        .foregroundColor(C.text)
        .presentationDetents([.height(170)])
        .task { await start() }
        .onReceive(tick) { _ in
            playing = clip.timeControlStatus == .playing
            if let d = clip.currentItem?.duration.seconds, d.isFinite, d > 0 { len = d }
            if !dragging { pos = clip.currentTime().seconds.isFinite ? clip.currentTime().seconds : 0 }
        }
        .onDisappear { clip.pause(); clip.replaceCurrentItem(with: nil) }
    }

    private func start() async {
        var link = track.previewUrl
        if link.isEmpty { link = (try? await Bridge.call("preview_url", [track.artist, track.title])) as? String ?? "" }
        guard !link.isEmpty, let url = URL(string: link) else { missing = true; return }
        player.pause()
        clip.replaceCurrentItem(with: AVPlayerItem(url: url))
        clip.play()
    }

    private func clock(_ s: Double) -> String {
        let n = Int(max(0, s)); return "\(n / 60):" + String(format: "%02d", n % 60)
    }
}
