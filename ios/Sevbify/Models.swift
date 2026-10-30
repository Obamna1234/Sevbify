import Foundation

/// A song (or podcast episode / audiobook chapter). Either a file on this iPhone (localPath set) or one you don't
/// have yet, which streams in full while online and can be downloaded - the same idea as the other apps.
struct Track: Codable, Hashable, Identifiable {
    var uid = UUID()
    var title: String
    var artist: String
    var album = ""
    var durationMs = 0
    var coverUrl = ""
    var previewUrl = ""
    var streamUrl = ""
    var downloadUrl = ""
    var source = ""
    var sourceId = ""
    var pageUrl = ""
    var genre = ""
    var explicit = false
    var key = ""
    /// "docs:Music/Artist/Song.m4a" (inside Sevbify's own folder) or "link:<folder id>/<path>" (a folder you added).
    var localPath = ""
    var localArt = ""

    var id: UUID { uid }
    var isLocal: Bool { !localPath.isEmpty }
    /// Podcast episodes, audiobook chapters and YouTube episodes (they remember where you stopped).
    var isItem: Bool { ["podcast", "audiobook", "youtube"].contains(source) }
    var itemKey: String { isItem ? "\(source):\(sourceId)" : "" }
    var matchKey: String { key.isEmpty ? Track.matchKey(artist, title) : key }
    var art: String { localArt.isEmpty ? coverUrl : localArt }

    init(title: String, artist: String) { self.title = title; self.artist = artist }

    init(dict d: [String: Any]) {
        func s(_ k: String) -> String { (d[k] as? String) ?? (d[k].map { "\($0)" } ?? "") }
        title = s("title"); artist = s("artist"); album = s("album")
        durationMs = (d["duration_ms"] as? NSNumber)?.intValue ?? 0
        coverUrl = s("cover_url"); previewUrl = s("preview_url"); streamUrl = s("stream_url")
        downloadUrl = s("download_url"); source = s("source"); sourceId = s("source_id"); pageUrl = s("page_url")
        genre = s("genre"); explicit = (d["explicit"] as? Bool) ?? false; key = s("key")
        localPath = s("local_path"); localArt = s("local_art")
    }

    /// The form the shared Python code understands (OnlineTrack.to_dict).
    var dict: [String: Any] {
        var d: [String: Any] = ["title": title, "artist": artist]
        if !album.isEmpty { d["album"] = album }
        if durationMs > 0 { d["duration_ms"] = durationMs }
        for (k, v) in [("cover_url", coverUrl), ("preview_url", previewUrl), ("stream_url", streamUrl),
                       ("download_url", downloadUrl), ("source", source), ("source_id", sourceId),
                       ("page_url", pageUrl), ("genre", genre), ("key", key)] where !v.isEmpty { d[k] = v }
        if explicit { d["explicit"] = true }
        return d
    }

    // Old saves stay readable when fields are added: everything except title/artist is optional.
    enum CodingKeys: String, CodingKey {
        case title, artist, album, durationMs, coverUrl, previewUrl, streamUrl, downloadUrl, source, sourceId,
             pageUrl, genre, explicit, key, localPath, localArt
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func s(_ k: CodingKeys) -> String { (try? c.decodeIfPresent(String.self, forKey: k)) ?? "" }
        title = s(.title); artist = s(.artist); album = s(.album)
        durationMs = (try? c.decodeIfPresent(Int.self, forKey: .durationMs)) ?? 0
        coverUrl = s(.coverUrl); previewUrl = s(.previewUrl); streamUrl = s(.streamUrl); downloadUrl = s(.downloadUrl)
        source = s(.source); sourceId = s(.sourceId); pageUrl = s(.pageUrl); genre = s(.genre)
        explicit = (try? c.decodeIfPresent(Bool.self, forKey: .explicit)) ?? false
        key = s(.key); localPath = s(.localPath); localArt = s(.localArt)
    }

    static func == (a: Track, b: Track) -> Bool { a.uid == b.uid }
    func hash(into h: inout Hasher) { h.combine(uid) }

    /// A copy with its own identity (the same song can be in a list twice).
    func fresh() -> Track { var t = self; t.uid = UUID(); return t }

    /// Same idea as core/online/models.match_key: first artist + title, lower-case, without versions.
    static func matchKey(_ artist: String, _ title: String) -> String {
        func norm(_ t: String) -> String {
            var s = t.lowercased()
            s = s.replacingOccurrences(of: #"\s*[\(\[](feat|ft|with|remaster|live|radio edit|official)[^)\]]*[\)\]]"#,
                                       with: "", options: .regularExpression)
            s = s.replacingOccurrences(of: #"\s+-\s+(remaster|live|radio edit).*$"#, with: "", options: .regularExpression)
            s = s.replacingOccurrences(of: "&", with: " and ")
            s = s.replacingOccurrences(of: #"[^\p{L}\p{N}\s]"#, with: " ", options: .regularExpression)
            s = s.replacingOccurrences(of: #"^the\s+"#, with: "", options: .regularExpression)
            s = s.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
            return s.trimmingCharacters(in: .whitespaces)
        }
        let first = artist.components(separatedBy: CharacterSet(charactersIn: ",;&")).first ?? artist
        let cleaned = first.replacingOccurrences(of: #"\s+(x|feat\.?|ft\.?)\s+.*$"#, with: "", options: .regularExpression)
        return "\(norm(cleaned))|\(norm(title))"
    }
}

struct Playlist: Codable, Identifiable, Hashable {
    var id = UUID().uuidString
    var name: String
    var tracks: [Track] = []
    var coverUrl = ""
    var created = Date().timeIntervalSince1970
    var lastPlayed: Double = 0
    var pinned = false
    /// "" made in Sevbify, or imported: "spotify" | "apple" | "deezer" | "jamendo" | "file"
    var origin = ""

    init(name: String, tracks: [Track] = []) { self.name = name; self.tracks = tracks }

    enum CodingKeys: String, CodingKey { case id, name, tracks, coverUrl, created, lastPlayed, pinned, origin }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = (try? c.decode(String.self, forKey: .id)) ?? UUID().uuidString
        name = (try? c.decode(String.self, forKey: .name)) ?? "Playlist"
        tracks = (try? c.decode([Track].self, forKey: .tracks)) ?? []
        coverUrl = (try? c.decode(String.self, forKey: .coverUrl)) ?? ""
        created = (try? c.decode(Double.self, forKey: .created)) ?? 0
        lastPlayed = (try? c.decode(Double.self, forKey: .lastPlayed)) ?? 0
        pinned = (try? c.decode(Bool.self, forKey: .pinned)) ?? false
        origin = (try? c.decode(String.self, forKey: .origin)) ?? ""
    }

    static func == (a: Playlist, b: Playlist) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }

    /// Spotify's picture for a playlist without one (same rule as core/playlist_cover.py): the covers of the
    /// first 4 different albums as a 2x2 grid; fewer than 4 → the first song's cover alone.
    var covers: [String] {
        if !coverUrl.isEmpty { return [coverUrl] }
        var seen = Set<String>(), picks: [String] = [], first = ""
        for t in tracks {
            let art = t.art
            if art.isEmpty { continue }
            if first.isEmpty { first = art }
            let album = t.album.trimmingCharacters(in: .whitespaces).lowercased()
            let key = (!album.isEmpty && album != "unknown album") ? "a|\(album)|\(t.artist.lowercased())" : "c|\(art)"
            if seen.insert(key).inserted { picks.append(art) }
            if picks.count == 4 { return picks }
        }
        return first.isEmpty ? [] : [first]
    }

    var totalMs: Int { tracks.reduce(0) { $0 + $1.durationMs } }
}

func formatTime(_ ms: Int) -> String {
    let s = max(0, ms / 1000)
    return String(format: "%d:%02d", s / 60, s % 60)
}

/// Spotify's phone app: "2h 48min", or "23min 5s" under an hour.
func formatTotal(_ ms: Int) -> String {
    let s = max(0, ms / 1000), h = s / 3600, m = (s % 3600) / 60
    return h > 0 ? "\(h)h \(m)min" : "\(m)min \(s % 60)s"
}
