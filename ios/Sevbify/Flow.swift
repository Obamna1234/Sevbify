import SwiftUI

/// Playlist ••• → Sort by energy…: three big cards (the same as the computer and Android; the ordering is
/// core/flow_order.py). A new playlist "<name> · Energetic to calm" (etc.) is made in that order. The original
/// playlist isn't touched, and songs in the new one can be moved or removed as usual.
struct FlowView: View {
    let playlist: Playlist
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @Environment(\.dismiss) var dismiss
    @State private var mode = "wind_down"
    @State private var working = false
    @State private var progress = 0.0
    @State private var note = ""

    private let cards: [(String, String, String)] = [
        ("wind_down", "Energetic → Easing down → Calm", "The most energetic songs first, settling down to the calmest."),
        ("build", "Calm → Ramping up → Energetic", "Starts with the calmest songs and builds up to the most energetic."),
        ("mix", "Mixed energies throughout", "Calm, in-between and energetic songs spread all the way through."),
    ]
    private let short = ["wind_down": "Energetic to calm", "build": "Calm to energetic", "mix": "Mixed energies"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Capsule().fill(Color(white: 0.37)).frame(width: 36, height: 4).frame(maxWidth: .infinity).padding(.top, 8)
                HStack(spacing: 12) {
                    PlaylistCover(playlist: playlist, size: 48)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Sort by energy").font(.title2.bold())
                        Text("\(playlist.name) · \(playlist.tracks.count) songs").font(.caption).foregroundColor(C.dim)
                    }
                }
                Text("Sorting by energy makes a copy of this playlist, with the songs arranged in the energy flow you choose. Your original playlist stays exactly as it is.")
                    .font(.subheadline).foregroundColor(C.dim)
                ForEach(cards, id: \.0) { key, name, text in
                    let on = mode == key
                    Button { mode = key } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            EnergyShape(mode: key).stroke(on ? C.green : Color.white,
                                                          style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
                                .frame(height: 50).padding(.horizontal, 4)
                            HStack { Text("Start"); Spacer(); Text("End") }.font(.system(size: 10)).foregroundColor(.gray)
                            Text(name).font(.headline.weight(.heavy)).padding(.top, 6)
                            Text(text).font(.footnote).foregroundColor(C.dim)
                        }
                        .padding(16)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 12).fill(on
                            ? AnyShapeStyle(LinearGradient(colors: [Color(red: 0.12, green: 0.23, blue: 0.16), Color(white: 0.14)],
                                                           startPoint: .top, endPoint: .bottom))
                            : AnyShapeStyle(Color(white: 0.165))))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(on ? C.green : Color.clear, lineWidth: 2))
                        .overlay(alignment: .topTrailing) {
                            if on {
                                Image(systemName: "checkmark").font(.caption.weight(.black)).foregroundColor(.black)
                                    .frame(width: 22, height: 22).background(Circle().fill(C.green)).padding(12)
                            }
                        }
                    }.buttonStyle(.plain).disabled(working)
                }
                if working || !note.isEmpty {
                    if working { ProgressView(value: progress).tint(C.green) }
                    Text(note).font(.caption).foregroundColor(C.dim)
                }
                Button { Task { await go() } } label: {
                    Text("Create sorted playlist").font(.headline.weight(.heavy)).foregroundColor(.black)
                        .frame(maxWidth: .infinity).padding(.vertical, 14).background(Capsule().fill(C.green))
                }.buttonStyle(.plain).disabled(working).padding(.top, 4)
                Button("Cancel") { dismiss() }.font(.subheadline.bold()).foregroundColor(.white)
                    .frame(maxWidth: .infinity).disabled(working)
            }
            .padding(.horizontal, 16).padding(.bottom, 20)
        }
        .foregroundColor(.white)
        .background(C.elevated.ignoresSafeArea())
        .interactiveDismissDisabled(working)
    }

    private func go() async {
        working = true
        let songs = playlist.tracks
        var feats: [Any] = []
        do {
            var start = 0
            while start < songs.count {
                let chunk = Array(songs[start..<min(start + 10, songs.count)])
                note = "Sorting by energy: \(min(start + 10, songs.count)) of \(songs.count) songs…"
                feats.append(contentsOf: try await Bridge.list("flow_features", [Bridge.json(chunk.map(\.dict))]))
                start += 10
                progress = Double(min(start, songs.count)) / Double(max(songs.count, 1))
            }
            let res = try await Bridge.object("flow_order", [Bridge.json(songs.map(\.dict)), Bridge.json(feats), mode, true, "calm"])
            let order = (res["order"] as? [Int]) ?? []
            guard order.count == songs.count else { throw NSError(domain: "Sort by energy", code: 1) }
            let pl = lib.newPlaylist("\(playlist.name) · \(short[mode] ?? "Sorted")", tracks: order.map { songs[$0].fresh() })
            let modeName = res["mode_name"] as? String ?? ""
            lib.update(pl.id) { $0.description = "“\(playlist.name)” sorted by energy: \(modeName). Drag songs to change it." }
            working = false
            dismiss()
            nav.go(.playlist(pl.id))
            Player.shared.status = "Made “\(pl.name)”. Your original playlist wasn't changed."
        } catch {
            working = false
            note = "Sorting by energy didn't work: \(error.localizedDescription)"
        }
    }
}

/// How the energy moves from the first song (left) to the last (right); y 0 = energetic.
struct EnergyShape: Shape {
    let mode: String
    func path(in r: CGRect) -> Path {
        let pts: [(CGFloat, CGFloat)]
        switch mode {
        case "build": pts = [(0, 0.8), (0.25, 0.76), (0.45, 0.55), (0.7, 0.3), (1, 0.12)]
        case "mix": pts = [(0, 0.5), (0.09, 0.2), (0.18, 0.7), (0.27, 0.3), (0.36, 0.82), (0.45, 0.15), (0.55, 0.6),
                           (0.64, 0.25), (0.73, 0.78), (0.82, 0.2), (0.91, 0.66), (1, 0.4)]
        default: pts = [(0, 0.12), (0.25, 0.16), (0.45, 0.38), (0.7, 0.62), (1, 0.8)]
        }
        let p = pts.map { CGPoint(x: r.minX + $0.0 * r.width, y: r.minY + $0.1 * r.height) }
        var path = Path()
        path.move(to: p[0])
        for (a, b) in zip(p, p.dropFirst()) {
            if mode == "mix" { path.addLine(to: b) }
            else { let m = (a.x + b.x) / 2; path.addCurve(to: b, control1: CGPoint(x: m, y: a.y), control2: CGPoint(x: m, y: b.y)) }
        }
        return path
    }
}
