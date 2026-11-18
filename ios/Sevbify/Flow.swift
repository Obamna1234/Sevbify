import SwiftUI

/// Playlist ••• → Flow this playlist…: choose how the songs should flow; a new playlist "<name> · Flow" is made in
/// that order (the same as the computer and Android; the ordering is core/flow_order.py). The original playlist
/// isn't touched, and songs in the new one can be moved or removed as usual.
struct FlowView: View {
    let playlist: Playlist
    @EnvironmentObject var lib: Library
    @EnvironmentObject var nav: Nav
    @Environment(\.dismiss) var dismiss
    @State private var mode = "wind_down"
    @State private var apart = true
    @State private var energetic = false
    @State private var working = false
    @State private var progress = 0.0
    @State private var note = ""

    private let modes: [(String, String, String)] = [
        ("wind_down", "Energy to calm", "Big, exciting songs first, then the middle ones, ending calm. (Default)"),
        ("build", "Calm to energy", "Starts calm and builds up to the big, exciting songs: good for workouts or getting ready."),
        ("waves", "Waves", "Builds up, eases off, builds up again: hot, cold, hot, cold."),
        ("smooth", "Smooth", "Every song leads gently into the next; genres blend instead of jumping."),
        ("mix", "Mix it up", "A bit of everything: calm, energetic and in-between songs spread through, shuffled."),
        ("genre", "Grouped by genre", "All the synthwave together, then the rock and so on, each smooth inside."),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Puts the \(playlist.tracks.count) songs of “\(playlist.name)” in an order that's nice to listen to, using each song's tempo, loudness and style (synthwave, chillwave, soft rock, metal…). It makes a new playlist, “\(playlist.name) · Flow”: yours stays exactly as it is, and you can move songs around in the new one.")
                        .font(.subheadline).foregroundColor(C.dim)
                    ForEach(modes, id: \.0) { key, name, text in
                        Button { mode = key } label: {
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: mode == key ? "largecircle.fill.circle" : "circle")
                                    .foregroundColor(mode == key ? C.green : C.dim).font(.title3)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(name).font(.headline)
                                    Text(text).font(.caption).foregroundColor(C.dim)
                                }
                                Spacer(minLength: 0)
                            }
                            .padding(12)
                            .background(RoundedRectangle(cornerRadius: 8).fill(mode == key ? Color(white: 0.17) : Color(white: 0.12)))
                        }.buttonStyle(.plain).disabled(working)
                    }
                    Toggle("Don't play the same artist twice in a row", isOn: $apart).tint(C.green).disabled(working)
                    Picker("Start with", selection: $energetic) {
                        Text("Start calm").tag(false)
                        Text("Start energetic").tag(true)
                    }.pickerStyle(.segmented).disabled(working)
                    if working || !note.isEmpty {
                        if working { ProgressView(value: progress).tint(C.green) }
                        Text(note).font(.caption).foregroundColor(C.dim)
                    }
                    Button { Task { await go() } } label: {
                        Text("Make Flow playlist").font(.headline).foregroundColor(.black)
                            .frame(maxWidth: .infinity).padding(.vertical, 13).background(Capsule().fill(C.green))
                    }.buttonStyle(.plain).disabled(working).padding(.top, 6)
                }
                .padding(20)
            }
            .foregroundColor(.white)
            .background(C.elevated.ignoresSafeArea())
            .navigationTitle("Flow this playlist").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() }.disabled(working) } }
        }
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
                note = "Listening to \(min(start + 10, songs.count)) of \(songs.count) songs…"
                feats.append(contentsOf: try await Bridge.list("flow_features", [Bridge.json(chunk.map(\.dict))]))
                start += 10
                progress = Double(min(start, songs.count)) / Double(max(songs.count, 1))
            }
            let res = try await Bridge.object("flow_order", [Bridge.json(songs.map(\.dict)), Bridge.json(feats), mode,
                                                             apart, energetic ? "energetic" : "calm"])
            let order = (res["order"] as? [Int]) ?? []
            guard order.count == songs.count else { throw NSError(domain: "Flow", code: 1) }
            let pl = lib.newPlaylist("\(playlist.name) · Flow", tracks: order.map { songs[$0].fresh() })
            let summary = res["summary"] as? String ?? "", modeName = res["mode_name"] as? String ?? "Flow"
            lib.update(pl.id) { $0.description = "\(modeName) order of “\(playlist.name)”: \(summary). Drag songs to change it." }
            working = false
            dismiss()
            nav.go(.playlist(pl.id))
            Player.shared.status = "Made “\(pl.name)”. Your original playlist wasn't changed."
        } catch {
            working = false
            note = "Flow didn't work: \(error.localizedDescription)"
        }
    }
}
