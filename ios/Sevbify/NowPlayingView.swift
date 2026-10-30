import SwiftUI
import AVKit

struct NowPlayingView: View {
    @EnvironmentObject var player: Player
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @Environment(\.dismiss) var dismiss
    @State private var dragging: Double? = nil
    @State private var showQueue = false
    @State private var menu = false

    var body: some View {
        let t = player.current
        VStack(spacing: 0) {
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
                Cover(url: t?.art ?? "", size: side, corner: 8)
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
                Slider(value: Binding(get: { dragging ?? player.position },
                                      set: { dragging = $0 }),
                       in: 0...max(1, player.duration),
                       onEditingChanged: { editing in
                           if !editing, let d = dragging { player.seek(to: d); dragging = nil }
                       })
                .tint(.white)
                HStack {
                    Text(formatTime(Int((dragging ?? player.position) * 1000)))
                    Spacer()
                    Text(player.isPreview ? "Preview" : formatTime(Int(player.duration * 1000)))
                }.font(.caption).foregroundColor(C.dim)
            }.padding(.horizontal, 24).padding(.top, 12)

            HStack {
                Button { player.toggleShuffle() } label: {
                    Image(systemName: "shuffle").font(.title3).foregroundColor(player.shuffle ? C.green : .white)
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
                RoutePicker().frame(width: 44, height: 44).accessibilityLabel("Connect to a device")
                Spacer()
                if let t, !t.isItem {
                    Button { player.startRadio(t) } label: { Image(systemName: "dot.radiowaves.left.and.right") }
                        .accessibilityLabel("Song radio")
                    Spacer()
                }
                Button { showQueue = true } label: { Image(systemName: "list.bullet") }.accessibilityLabel("Queue")
            }.font(.title3).padding(.horizontal, 24).padding(.vertical, 16)
        }
        .foregroundColor(.white)
        .background(
            LinearGradient(colors: [Color(red: 0.25, green: 0.2, blue: 0.25), C.bg], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea())
        .sheet(isPresented: $showQueue) { QueueView() }
        .sheet(isPresented: $menu) { if let t { TrackMenu(track: t).presentationDetents([.medium, .large]) } }
    }
}

/// AirPlay / Bluetooth speakers and headphones (Apple's own picker, like Spotify's Connect button).
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
