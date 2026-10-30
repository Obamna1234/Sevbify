import AVFoundation
import Combine
import MediaPlayer
import UIKit

/// Sevbify's queue and playback, like the other apps: a context (playlist, album, radio, search...), "Add to
/// queue" songs that play next, shuffle and repeat. Songs you have play from the iPhone; others stream in full
/// while online (found on Bandcamp, then YouTube), or as 30-second previews. Lock screen and Control Centre work.
@MainActor
final class Player: ObservableObject {
    static let shared = Player()

    @Published private(set) var context: [Track] = []
    @Published private(set) var index = 0
    @Published var userQueue: [Track] = []
    @Published private(set) var sourceName = ""
    @Published private(set) var isPlaying = false
    @Published private(set) var loading = false
    @Published var position: Double = 0          // seconds
    @Published private(set) var duration: Double = 0
    @Published var status = ""
    @Published private(set) var isPreview = false

    var shuffle: Bool { Library.shared.settings.shuffle }
    var repeatMode: String { Library.shared.settings.repeatMode }
    var current: Track? { context.indices.contains(index) ? context[index] : nil }
    var upcoming: [Track] { context.indices.contains(index) ? Array(context[(index + 1)...]) : [] }

    private let player = AVPlayer()
    private var original: [Track] = []
    private var generation = 0
    private var failuresInARow = 0
    private var observers: [Any] = []
    private var itemObserver: AnyCancellable?
    private var artwork: (String, MPMediaItemArtwork)?

    private init() {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        player.automaticallyWaitsToMinimizeStalling = true
        let tick = player.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.5, preferredTimescale: 600), queue: .main) { [weak self] time in
            Task { @MainActor in
                guard let self else { return }
                self.position = time.seconds.isFinite ? time.seconds : 0
                if let d = self.player.currentItem?.duration.seconds, d.isFinite, d > 0 { self.duration = d }
                self.isPlaying = self.player.timeControlStatus == .playing
                if let t = self.current, t.isItem, self.position > 5 { Library.shared.resume[t.itemKey] = self.position }
            }
        }
        observers.append(tick)
        let nc = NotificationCenter.default
        observers.append(nc.addObserver(forName: .AVPlayerItemDidPlayToEndTime, object: nil, queue: .main) { [weak self] note in
            Task { @MainActor in
                guard let self, (note.object as? AVPlayerItem) === self.player.currentItem else { return }
                if let t = self.current, t.isItem { Library.shared.resume[t.itemKey] = nil }
                self.advance(auto: true)
            }
        })
        observers.append(nc.addObserver(forName: AVAudioSession.interruptionNotification, object: nil, queue: .main) { [weak self] note in
            Task { @MainActor in
                guard let self, let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                      AVAudioSession.InterruptionType(rawValue: raw) == .ended else { return }
                let opts = note.userInfo?[AVAudioSessionInterruptionOptionKey] as? UInt ?? 0
                if AVAudioSession.InterruptionOptions(rawValue: opts).contains(.shouldResume) { self.player.play() }
            }
        })
        setUpRemoteCommands()
    }

    // --- choosing what plays ----------------------------------------------------------------------------------
    func play(_ track: Track, in list: [Track], source: String) {
        var items = list.isEmpty ? [track] : list
        var start = items.firstIndex(where: { $0.uid == track.uid }) ?? items.firstIndex(where: { $0.matchKey == track.matchKey }) ?? 0
        original = items
        if shuffle && !items.allSatisfy({ $0.isItem }) {
            let first = items.remove(at: start)
            items = [first] + items.shuffled()
            start = 0
        }
        context = items
        index = start
        sourceName = source
        failuresInARow = 0
        startCurrent()
    }

    func playAll(_ list: [Track], source: String, shuffled: Bool = false) {
        guard !list.isEmpty else { return }
        if shuffled != shuffle { Library.shared.settings.shuffle = shuffled }
        play(shuffled ? list.randomElement()! : list[0], in: list, source: source)
    }

    func addToQueue(_ t: Track) { userQueue.append(t.fresh()); status = "Added to queue" }
    func playNext(_ t: Track) { userQueue.insert(t.fresh(), at: 0); status = "Plays next" }

    func jump(to t: Track) {
        if let i = context.firstIndex(where: { $0.uid == t.uid }) { index = i; startCurrent() }
        else if let i = userQueue.firstIndex(where: { $0.uid == t.uid }) {
            let picked = userQueue.remove(at: i)
            context.insert(picked, at: min(index + 1, context.count)); index += 1; startCurrent()
        }
    }

    // --- controls -------------------------------------------------------------------------------------------
    func toggle() {
        if current == nil { return }
        if player.currentItem == nil { startCurrent(); return }
        if player.timeControlStatus == .playing { player.pause() } else { activate(); player.play() }
        isPlaying.toggle()
        updateNowPlaying()
    }

    func pause() { player.pause(); isPlaying = false; updateNowPlaying() }

    func next() { radioSkipFeedback(); advance(auto: false) }

    func previous() {
        if position > 3 || index == 0 { seek(to: 0); return }
        index -= 1
        startCurrent()
    }

    func seek(to seconds: Double) {
        player.seek(to: CMTime(seconds: seconds, preferredTimescale: 600))
        position = seconds
        updateNowPlaying()
    }

    func toggleShuffle() {
        Library.shared.settings.shuffle.toggle()
        guard let cur = current else { return }
        if shuffle && !context.allSatisfy({ $0.isItem }) {
            let head = Array(context.prefix(index + 1)), rest = Array(context.dropFirst(index + 1)).shuffled()
            context = head + rest
        } else if !original.isEmpty {
            context = original
            index = context.firstIndex(where: { $0.uid == cur.uid }) ?? 0
        }
    }

    func cycleRepeat() {
        let next = ["off": "all", "all": "one"][repeatMode] ?? "off"
        Library.shared.settings.repeatMode = next
    }

    // --- radio ----------------------------------------------------------------------------------------------
    func startRadio(_ seed: Track, autoplay: Bool = false) {
        status = "Starting \(seed.title) Radio…"
        Task {
            do {
                var songs = try await Bridge.tracks("radio", [seed.artist, seed.title, 50])
                if !Library.shared.settings.explicitOk { songs = songs.filter { !$0.explicit } }
                guard !songs.isEmpty else { status = "No radio for this song"; return }
                let list = autoplay ? songs : [seed.fresh()] + songs
                Library.shared.settings.shuffle = false
                play(list[0], in: list, source: "\(seed.title) Radio")
                status = autoplay ? "Autoplay: \(seed.title) Radio" : ""
                if !autoplay { Nav.current?.go(.radio("\(seed.title) Radio", list)) }   // its own page, like Spotify
            } catch {
                status = "Radio needs the internet (\(error.localizedDescription))"
            }
        }
    }

    /// Skipping a radio song in its first 30 s: less of that artist for the rest of this radio, like Spotify.
    /// Kept in memory only (nothing saved or sent). Same rule as the Windows and Android apps.
    private func radioSkipFeedback() {
        guard let t = current, sourceName.hasSuffix(" Radio"), userQueue.isEmpty, !t.isItem, index > 0,
              position < 30 else { return }
        let artist = t.artist.trimmingCharacters(in: .whitespaces).lowercased()
        let rest = Array(context.dropFirst(index + 1))
        let kept = rest.filter { $0.artist.trimmingCharacters(in: .whitespaces).lowercased() != artist }
        guard kept.count != rest.count, kept.count >= 5 else { return }
        let removed = Set(rest.filter { !kept.contains($0) }.map { $0.uid })
        context = Array(context.prefix(index + 1)) + kept
        original.removeAll { removed.contains($0.uid) }
        status = "Got it: less \(t.artist) on this radio"
    }

    // --- moving through the queue ---------------------------------------------------------------------------
    private func advance(auto: Bool, failed: Bool = false) {
        if failed {
            failuresInARow += 1
            if failuresInARow >= max(1, context.count + userQueue.count) {
                pause()
                status = Library.shared.settings.online ? "Nothing in this list could be played"
                    : "You're offline and none of these songs are downloaded"
                return
            }
        } else { failuresInARow = 0 }
        if auto && repeatMode == "one" && !failed { seek(to: 0); player.play(); return }
        if !userQueue.isEmpty {
            let t = userQueue.removeFirst()
            context.insert(t, at: min(index + 1, context.count))
            index += 1
            startCurrent(); return
        }
        if index + 1 < context.count { index += 1; startCurrent(); return }
        if !context.isEmpty && (repeatMode == "all" || (!auto && !failed)) { index = 0; startCurrent(); return }
        let s = Library.shared.settings
        if auto, s.autoplay, s.online, let last = current, !last.isItem {
            startRadio(last, autoplay: true)            // keep playing similar songs, like Spotify
        } else {
            pause()
        }
    }

    // --- getting a song to play -----------------------------------------------------------------------------
    private func activate() { try? AVAudioSession.sharedInstance().setActive(true) }

    private func startCurrent() {
        guard let t = current else { return }
        generation += 1
        let gen = generation
        player.pause()
        player.replaceCurrentItem(with: nil)
        position = Double(Library.shared.resume[t.itemKey] ?? 0)
        duration = Double(t.durationMs) / 1000
        loading = true
        isPreview = false
        status = ""
        updateNowPlaying()
        if !t.isItem { Library.shared.addRecent(t) }
        Task {
            do {
                let (asset, preview) = try await resolve(t)
                guard gen == generation else { return }
                let item = AVPlayerItem(asset: asset)
                itemObserver = item.publisher(for: \.status).receive(on: DispatchQueue.main).sink { [weak self] st in
                    Task { @MainActor in
                        guard let self, gen == self.generation else { return }
                        if st == .failed {
                            self.loading = false
                            self.status = "Couldn't play \(t.title): \(item.error?.localizedDescription ?? "unknown error")"
                            self.advance(auto: true, failed: true)
                        } else if st == .readyToPlay {
                            self.loading = false
                        }
                    }
                }
                activate()
                player.replaceCurrentItem(with: item)
                if let at = Library.shared.resume[t.itemKey], at > 5 {
                    _ = await player.seek(to: CMTime(seconds: at, preferredTimescale: 600))
                }
                player.play()
                isPlaying = true
                isPreview = preview
                if preview { status = "30-second preview (full song not found)" }
                updateNowPlaying()
            } catch {
                guard gen == generation else { return }
                loading = false
                status = "Couldn't play \(t.title): \(error.localizedDescription)"
                advance(auto: true, failed: true)
            }
        }
    }

    private struct NoSource: LocalizedError {
        let errorDescription: String?
    }

    /// (what to play, is it only a preview)
    private func resolve(_ t: Track) async throws -> (AVURLAsset, Bool) {
        let lib = Library.shared
        if let local = lib.localFor(t), let url = lib.url(for: local), FileManager.default.fileExists(atPath: url.path) {
            return (AVURLAsset(url: url), false)
        }
        guard lib.settings.online else { throw NoSource(errorDescription: "you're offline and it isn't downloaded") }
        if !t.streamUrl.isEmpty, let url = URL(string: httpsFirst(t.streamUrl)) {
            return (AVURLAsset(url: url), false)                                    // podcast episode / chapter
        }
        if t.source == "youtube", !t.pageUrl.isEmpty {
            let o = try await Bridge.object("youtube_stream", [t.pageUrl, false])
            return (try asset(o), false)
        }
        if lib.settings.streamFull {
            do {
                let o = try await Bridge.object("resolve", [t.artist, t.title, t.durationMs])
                return (try asset(o), false)
            } catch {
                if t.previewUrl.isEmpty { throw error }
                NSLog("Sevbify: full song not found for %@: %@", t.title, error.localizedDescription)
            }
        }
        if let url = URL(string: t.previewUrl), !t.previewUrl.isEmpty { return (AVURLAsset(url: url), true) }
        throw NoSource(errorDescription: "no full song or preview found")
    }

    private func asset(_ o: [String: Any]) throws -> AVURLAsset {
        guard let s = o["url"] as? String, let url = URL(string: s) else { throw NoSource(errorDescription: "no link") }
        let headers = (o["headers"] as? [String: String]) ?? [:]
        return AVURLAsset(url: url, options: headers.isEmpty ? nil : ["AVURLAssetHTTPHeaderFieldsKey": headers])
    }

    private func httpsFirst(_ s: String) -> String { s.hasPrefix("http://") ? "https://" + s.dropFirst(7) : s }

    // --- lock screen / Control Centre -----------------------------------------------------------------------
    private func setUpRemoteCommands() {
        let c = MPRemoteCommandCenter.shared()
        c.playCommand.addTarget { [weak self] _ in Task { @MainActor in self?.activate(); self?.player.play(); self?.isPlaying = true }; return .success }
        c.pauseCommand.addTarget { [weak self] _ in Task { @MainActor in self?.pause() }; return .success }
        c.togglePlayPauseCommand.addTarget { [weak self] _ in Task { @MainActor in self?.toggle() }; return .success }
        c.nextTrackCommand.addTarget { [weak self] _ in Task { @MainActor in self?.next() }; return .success }
        c.previousTrackCommand.addTarget { [weak self] _ in Task { @MainActor in self?.previous() }; return .success }
        c.changePlaybackPositionCommand.addTarget { [weak self] e in
            if let e = e as? MPChangePlaybackPositionCommandEvent { Task { @MainActor in self?.seek(to: e.positionTime) } }
            return .success
        }
    }

    private func updateNowPlaying() {
        guard let t = current else { MPNowPlayingInfoCenter.default().nowPlayingInfo = nil; return }
        var info: [String: Any] = [
            MPMediaItemPropertyTitle: t.title, MPMediaItemPropertyArtist: t.artist,
            MPMediaItemPropertyAlbumTitle: t.album,
            MPMediaItemPropertyPlaybackDuration: duration,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: position,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0,
        ]
        if let (key, art) = artwork, key == t.art { info[MPMediaItemPropertyArtwork] = art }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
        let wanted = t.art
        if !wanted.isEmpty && artwork?.0 != wanted, let url = URL(string: wanted) {
            Task {
                guard let (data, _) = try? await URLSession.shared.data(from: url), let img = UIImage(data: data) else { return }
                let art = MPMediaItemArtwork(boundsSize: img.size) { _ in img }
                artwork = (wanted, art)
                if current?.art == wanted { updateNowPlaying() }
            }
        }
    }
}
