import SwiftUI
import CryptoKit
import AVFoundation

/// Sevbify on this iPhone and Sevbify on a computer: paired by scanning the computer's QR code, then songs and
/// folders go either way over your own Wi-Fi. Same protocol and safety rules as the computer (core/pair_crypto.py,
/// core/pairing.py) with Apple's CryptoKit: P-256 ECDH + HKDF-SHA256 with the QR code's one-time code (later this
/// phone's own key), AES-256-GCM frames. Nothing goes through the internet; only local-network addresses are used.
/// Songs from the computer are saved only after you accept them, in Files → On My iPhone → Sevbify → From <name>.
enum PairCrypto {
    static let kindJSON: UInt8 = 1, kindData: UInt8 = 2
    static let maxFrame = 1 << 20

    static func hmac(_ key: Data, _ data: Data) -> Data {
        Data(HMAC<SHA256>.authenticationCode(for: data, using: SymmetricKey(data: key)))
    }
    static func sha256(_ d: Data) -> Data { Data(SHA256.hash(data: d)) }

    static func deriveKeys(secret: Data, psk: Data, mode: String, dev: String, cNonce: Data, sNonce: Data,
                           cEpk: Data, sEpk: Data, cHello: Data, sHello: Data) -> (Data, Data) {
        var salt = Data("sevbify-pair-v1".utf8) + Data(mode.utf8) + Data("|".utf8) + Data(dev.utf8) + Data("|".utf8)
        salt += cNonce + sNonce + cEpk + sEpk + sha256(cHello) + sha256(sHello)
        let prk = hmac(sha256(salt), secret + psk)
        var okm = Data(), block = Data(), i: UInt8 = 1
        while okm.count < 64 { block = hmac(prk, block + Data("sevbify v1 keys".utf8) + Data([i])); okm += block; i += 1 }
        return (okm.prefix(32), okm.subdata(in: 32..<64))
    }

    static func ecdh(_ priv: P256.KeyAgreement.PrivateKey, _ peer: Data) throws -> Data {
        let pub = try P256.KeyAgreement.PublicKey(x963Representation: peer)      // checks the point is on the curve
        return try priv.sharedSecretFromKeyAgreement(with: pub).withUnsafeBytes { Data($0) }
    }

    static func hex(_ s: String) -> Data {
        var d = Data(); var i = s.startIndex
        while i < s.endIndex { let j = s.index(i, offsetBy: 2); d.append(UInt8(s[i..<j], radix: 16)!); i = j }
        return d
    }
    static func toHex(_ d: Data) -> String { d.map { String(format: "%02x", $0) }.joined() }

    /// The computer's fixed test values (core/pair_crypto.test_vector) must give the same keys here.
    static func selfTest() -> Bool {
        guard let c = try? P256.KeyAgreement.PrivateKey(rawRepresentation: Data(repeating: 0x11, count: 32)) else { return false }
        let sEpk = hex("04d65a93977caa3d1b081852ff57a79e465f1660577304baead505dd3a48589cf350185e895372df6221ea3a137557e473fddb6755f05bd507c3c533fce9c91285")
        guard let secret = try? ecdh(c, sEpk) else { return false }
        let (c2s, s2c) = deriveKeys(secret: secret, psk: Data((0..<32).map { UInt8($0) }), mode: "pair", dev: "",
                                    cNonce: Data(repeating: 1, count: 32), sNonce: Data(repeating: 2, count: 32),
                                    cEpk: c.publicKey.x963Representation, sEpk: sEpk,
                                    cHello: hex("000000027b7d"), sHello: hex("000000035b315d"))
        let frame = (try? PairChannel(send: c2s, recv: s2c).seal(kindJSON, Data("{\"t\":\"ping\"}".utf8))) ?? Data()
        return toHex(c2s) == "8638dfdad0487dfde8d45c9487939f51f72828040e0c707ec4dfc5bdb4725b52" &&
            toHex(frame) == "0000001d66d891584379f9cd9fcd93c63311ea622004319f5c86f7e1c96a625ae2"
    }
}

final class PairChannel {
    private let sendKey: SymmetricKey, recvKey: SymmetricKey
    private var sendN: UInt64 = 0, recvN: UInt64 = 0
    private let lock = NSLock()
    init(send: Data, recv: Data) { sendKey = SymmetricKey(data: send); recvKey = SymmetricKey(data: recv) }

    private static func nonce(_ n: UInt64) throws -> AES.GCM.Nonce {
        var d = Data(repeating: 0, count: 4); var be = n.bigEndian
        d.append(Data(bytes: &be, count: 8))
        return try AES.GCM.Nonce(data: d)
    }

    func seal(_ kind: UInt8, _ payload: Data) throws -> Data {
        lock.lock(); defer { lock.unlock() }
        let box = try AES.GCM.seal(Data([kind]) + payload, using: sendKey, nonce: PairChannel.nonce(sendN))
        sendN += 1
        let body = box.ciphertext + box.tag
        var len = UInt32(body.count).bigEndian
        return Data(bytes: &len, count: 4) + body
    }

    func open(_ body: Data) throws -> (UInt8, Data) {
        guard body.count >= 17, body.count <= PairCrypto.maxFrame + 64 else { throw PairError.protocolError }
        let box = try AES.GCM.SealedBox(nonce: PairChannel.nonce(recvN), ciphertext: body.prefix(body.count - 16),
                                        tag: body.suffix(16))
        let plain = try AES.GCM.open(box, using: recvKey)          // throws unless made with the right key
        recvN += 1
        return (plain.first ?? 0, plain.dropFirst())
    }
}

enum PairError: Error { case protocolError, refused(String), unreachable }

struct PairCode: Equatable {
    let addresses: [String], port: Int, code: Data, pcId: String, name: String
}

struct PairedComputer: Codable {
    var name: String, pcId: String, addresses: [String], port: Int, dev: String, ltk: Data
}

struct IncomingOffer: Identifiable {
    let id: String, title: String, items: [(String, Int64)]
    var total: Int64 { items.reduce(0) { $0 + $1.1 } }
}

/// Blocking socket reads/writes on a background thread (the connection's own thread).
private final class PairSocket {
    let input: InputStream, output: OutputStream
    let host: String
    init?(host: String, port: Int) {
        var i: InputStream?, o: OutputStream?
        Stream.getStreamsToHost(withName: host, port: port, inputStream: &i, outputStream: &o)
        guard let i, let o else { return nil }
        input = i; output = o; self.host = host
        i.open(); o.open()
        let end = Date().addingTimeInterval(4)
        while Date() < end && (o.streamStatus == .opening || i.streamStatus == .opening) { Thread.sleep(forTimeInterval: 0.05) }
        if o.streamStatus != .open || i.streamStatus == .error { close(); return nil }
    }
    func write(_ d: Data) throws {
        var off = 0
        try d.withUnsafeBytes { (p: UnsafeRawBufferPointer) in
            while off < d.count {
                let n = output.write(p.baseAddress!.advanced(by: off).assumingMemoryBound(to: UInt8.self), maxLength: d.count - off)
                if n <= 0 { throw PairError.unreachable }
                off += n
            }
        }
    }
    func read(_ count: Int) throws -> Data {
        var d = Data(capacity: count)
        var buf = [UInt8](repeating: 0, count: min(count, 65536))
        while d.count < count {
            let n = input.read(&buf, maxLength: min(buf.count, count - d.count))
            if n <= 0 { throw PairError.unreachable }
            d.append(buf, count: n)
        }
        return d
    }
    func readInt() throws -> Int { let b = try read(4); return Int(b[0]) << 24 | Int(b[1]) << 16 | Int(b[2]) << 8 | Int(b[3]) }
    func close() { input.close(); output.close() }
}

@MainActor
final class PairLink: ObservableObject {
    static let shared = PairLink()
    @Published var computer: PairedComputer?
    @Published var status = ""
    @Published var offer: IncomingOffer?
    @Published var pendingCode: PairCode?
    @Published var progress = ""
    var connected: Bool { status == "Connected" }

    private static let audio: Set<String> = ["mp3", "m4a", "aac", "flac", "ogg", "opus", "wav", "wma", "aiff", "aif", "alac", "ape", "mka", "webm"]
    private static let extra: [String: Int64] = ["jpg": 30 << 20, "jpeg": 30 << 20, "png": 30 << 20, "lrc": 1 << 20, "m3u": 1 << 20, "m3u8": 1 << 20]
    private static let reserved: Set<String> = Set(["con", "prn", "aux", "nul", "conin$", "conout$", "clock$"] +
        "0123456789¹²³".flatMap { ["com\($0)", "lpt\($0)"] })
    private var file: URL { Library.support.appendingPathComponent("paired_computer.json") }
    private var worker: Thread?
    private nonisolated(unsafe) var sock: PairSocket?
    private nonisolated(unsafe) var channel: PairChannel?
    private nonisolated(unsafe) var stopFlag = false
    private nonisolated(unsafe) var receiving: [String: Receiving] = [:]
    private nonisolated(unsafe) var usedIds = Set<String>()
    private nonisolated(unsafe) var answers: [String: (Bool) -> Void] = [:]
    // Copies the connection's thread reads (the @Published ones belong to the main thread).
    private nonisolated(unsafe) var knownCopy: PairedComputer?
    private nonisolated(unsafe) var offerOpen = false
    private nonisolated(unsafe) var deviceName = "iPhone"
    private let lock = NSLock()

    init() {
        computer = try? JSONDecoder().decode(PairedComputer.self, from: Data(contentsOf: file))
        knownCopy = computer
    }

    // MARK: the QR code
    nonisolated static func isLocal(_ a: String) -> Bool {
        let p = a.split(separator: ".").compactMap { Int($0) }
        guard p.count == 4, p.allSatisfy({ (0...255).contains($0) }) else { return false }
        return p[0] == 10 || (p[0] == 172 && (16...31).contains(p[1])) || (p[0] == 192 && p[1] == 168) ||
            (p[0] == 169 && p[1] == 254) || p[0] == 127 || (p[0] == 100 && (64...127).contains(p[1]))
    }

    nonisolated static func parse(_ link: String) -> PairCode? {
        guard link.count <= 600, let u = URLComponents(string: link), u.scheme == "sevbify", u.host == "pair" else { return nil }
        let q = Dictionary((u.queryItems ?? []).map { ($0.name, $0.value ?? "") }, uniquingKeysWith: { a, _ in a })
        var s = (q["s"] ?? "").replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        s += String(repeating: "=", count: (4 - s.count % 4) % 4)
        guard let code = Data(base64Encoded: s), code.count == 32, let port = Int(q["p"] ?? ""), (1024...65535).contains(port)
        else { return nil }
        let addrs = (q["a"] ?? "").split(separator: ",").map(String.init).filter { isLocal($0) }.prefix(4)
        guard !addrs.isEmpty else { return nil }
        return PairCode(addresses: Array(addrs), port: port, code: code, pcId: String((q["id"] ?? "").prefix(32)),
                        name: cleanName(q["n"] ?? "", "Computer"))
    }

    nonisolated static func cleanName(_ name: String, _ fallback: String) -> String {
        let n = String(name.precomposedStringWithCanonicalMapping.unicodeScalars.filter {
            ![.control, .format, .surrogate, .privateUse, .unassigned].contains($0.properties.generalCategory) && !"<>&".unicodeScalars.contains($0)
        }.prefix(40)).trimmingCharacters(in: .whitespaces)
        return n.isEmpty ? fallback : n
    }

    // MARK: connection
    func start() {
        guard computer != nil, worker == nil else { return }
        deviceName = PairLink.cleanName(UIDevice.current.name, "iPhone")
        stopFlag = false
        let t = Thread { [weak self] in self?.loop(code: nil) }
        t.name = "sevbify-pair"; worker = t; t.start()
    }

    func pair(_ code: PairCode) {
        pendingCode = nil
        deviceName = PairLink.cleanName(UIDevice.current.name, "iPhone")
        stopAll()
        status = "Connecting…"
        stopFlag = false
        let t = Thread { [weak self] in self?.loop(code: code) }
        t.name = "sevbify-pair"; worker = t; t.start()
    }

    func stopAll() { stopFlag = true; sock?.close(); worker = nil }

    func forget() {
        stopAll()
        computer = nil; knownCopy = nil; status = ""
        try? FileManager.default.removeItem(at: file)
    }

    private func save(_ c: PairedComputer) {
        computer = c; knownCopy = c
        if let d = try? JSONEncoder().encode(c) { try? d.write(to: file, options: [.atomic, .completeFileProtection]) }
    }

    private nonisolated func setStatus(_ s: String) { Task { @MainActor in self.status = s } }

    private nonisolated func loop(code: PairCode?) {
        var code = code
        while !stopFlag {
            let known = knownCopy
            if code == nil && known == nil { break }
            do { try connect(code: code, known: known) } catch {
                if code != nil {
                    setStatus(known == nil ? "Couldn't pair: scan a new code on the computer" : "Can't reach \(code!.name)")
                } else if let k = known { setStatus("Can't reach \(k.name)") }
            }
            code = nil
            close()
            for _ in 0..<60 where !stopFlag { Thread.sleep(forTimeInterval: 0.5) }
        }
    }

    private nonisolated func close() {
        sock?.close(); sock = nil; channel = nil
        lock.lock(); receiving.values.forEach { $0.abort() }; receiving = [:]; let a = answers; answers = [:]; lock.unlock()
        a.values.forEach { $0(false) }
        offerOpen = false
        Task { @MainActor in self.offer = nil; if self.status == "Connected" { self.status = "" } }
    }

    private nonisolated func plainFrame(_ o: [String: Any]) -> Data {
        let b = (try? JSONSerialization.data(withJSONObject: o)) ?? Data()
        var len = UInt32(b.count).bigEndian
        return Data(bytes: &len, count: 4) + b
    }

    nonisolated func sendJSON(_ o: [String: Any]) throws {
        guard let ch = channel, let s = sock else { throw PairError.unreachable }
        let data = try ch.seal(PairCrypto.kindJSON, JSONSerialization.data(withJSONObject: o))
        lock.lock(); defer { lock.unlock() }
        try s.write(data)
    }

    private nonisolated func sendData(_ d: Data) throws {
        guard let ch = channel, let s = sock else { throw PairError.unreachable }
        let data = try ch.seal(PairCrypto.kindData, d)
        lock.lock(); defer { lock.unlock() }
        try s.write(data)
    }

    private nonisolated func connect(code: PairCode?, known: PairedComputer?) throws {
        let addrs = code?.addresses ?? known?.addresses ?? []
        let port = code?.port ?? known?.port ?? 0
        var s: PairSocket?
        outer: for a in addrs where PairLink.isLocal(a) {
            for p in [port] + (1...5).map({ port + $0 }) { if let x = PairSocket(host: a, port: p) { s = x; break outer } }
        }
        guard let s else { throw PairError.unreachable }
        sock = s
        let mode = code != nil ? "pair" : "resume"
        let dev = code != nil ? "" : (known?.dev ?? "")
        let priv = P256.KeyAgreement.PrivateKey()
        let cEpk = priv.publicKey.x963Representation
        var cNonce = Data(count: 32); _ = cNonce.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        let cHello = plainFrame(["t": "hello", "v": [1], "mode": mode, "dev": dev, "epk": cEpk.base64EncodedString(),
                                 "nonce": cNonce.base64EncodedString()])
        try s.write(cHello)
        let n = try s.readInt()
        guard (1...1024).contains(n) else { throw PairError.protocolError }
        let body = try s.read(n)
        let sHello = cHello.prefix(0) + Data([UInt8(n >> 24 & 255), UInt8(n >> 16 & 255), UInt8(n >> 8 & 255), UInt8(n & 255)]) + body
        guard let reply = try JSONSerialization.jsonObject(with: body) as? [String: Any] else { throw PairError.protocolError }
        if reply["t"] as? String == "error" { throw PairError.refused(reply["code"] as? String ?? "") }   // shown only
        guard reply["t"] as? String == "hello", reply["v"] as? Int == 1,
              let sEpk = Data(base64Encoded: reply["epk"] as? String ?? ""), sEpk.count == 65,
              let sNonce = Data(base64Encoded: reply["nonce"] as? String ?? ""), sNonce.count == 32 else { throw PairError.protocolError }
        let secret = try PairCrypto.ecdh(priv, sEpk)
        let psk = code?.code ?? known?.ltk ?? Data()
        let (c2s, s2c) = PairCrypto.deriveKeys(secret: secret, psk: psk, mode: mode, dev: dev, cNonce: cNonce, sNonce: sNonce,
                                               cEpk: cEpk, sEpk: sEpk, cHello: cHello, sHello: sHello)
        let ch = PairChannel(send: c2s, recv: s2c)
        channel = ch
        let version = Bundle.main.object(forInfoDictionaryKey: "SevbifyVersion") as? String ?? ""
        try sendJSON(["t": mode, "name": deviceName, "platform": "ios",
                      "app": version, "features": ["send_files"]])
        let (kind, payload) = try recvFrame(s, ch, limit: 8 * 1024)
        guard kind == PairCrypto.kindJSON, let info = try JSONSerialization.jsonObject(with: payload) as? [String: Any]
        else { throw PairError.protocolError }
        let name = PairLink.cleanName(info["name"] as? String ?? "", code?.name ?? known?.name ?? "Computer")
        let newPort = (info["port"] as? Int).flatMap { (1024...65535).contains($0) ? $0 : nil } ?? port
        switch info["t"] as? String {
        case "paired":
            guard let ltk = Data(base64Encoded: info["ltk"] as? String ?? ""), ltk.count == 32,
                  let devId = info["dev"] as? String, devId.count == 32, let code else { throw PairError.protocolError }
            let c = PairedComputer(name: name, pcId: String((info["pc_id"] as? String ?? "").prefix(32)),
                                   addresses: code.addresses, port: newPort, dev: devId, ltk: ltk)
            knownCopy = c
            Task { @MainActor in self.save(c) }
        case "welcome":
            guard var c = known else { throw PairError.protocolError }
            c.name = name; c.port = newPort
            c.addresses = [s.host] + c.addresses.filter { $0 != s.host }
            knownCopy = c
            let saved = c
            Task { @MainActor in self.save(saved) }
        default: throw PairError.protocolError
        }
        setStatus("Connected")
        let pinger = Thread { [weak self] in
            while let self, !self.stopFlag, self.sock === s { Thread.sleep(forTimeInterval: 60); try? self.sendJSON(["t": "ping"]) }
        }
        pinger.start()
        while !stopFlag {
            let (k, p) = try recvFrame(s, ch)
            if k == PairCrypto.kindData { try onData(p) } else if k == PairCrypto.kindJSON,
                let m = try JSONSerialization.jsonObject(with: p) as? [String: Any] { try handle(m) }
        }
    }

    private nonisolated func recvFrame(_ s: PairSocket, _ ch: PairChannel, limit: Int = PairCrypto.maxFrame + 64) throws -> (UInt8, Data) {
        let n = try s.readInt()
        guard n >= 17, n <= limit else { throw PairError.protocolError }
        return try ch.open(try s.read(n))
    }

    // MARK: receiving
    nonisolated static func safePart(_ part: String) -> String {
        var p = String(part.precomposedStringWithCanonicalMapping.unicodeScalars.filter {
            ![.control, .format, .surrogate, .privateUse, .unassigned].contains($0.properties.generalCategory)
        }.map { "<>:\"/\\|?*".unicodeScalars.contains($0) ? "_" : Character($0) })
        p = p.trimmingCharacters(in: .whitespaces)
        while p.hasSuffix(".") || p.hasSuffix(" ") { p.removeLast() }
        if p.isEmpty || p == "." || p == ".." { return "_" }
        let stem = (p.split(separator: ".", omittingEmptySubsequences: false).first.map(String.init) ?? "")
            .trimmingCharacters(in: CharacterSet(charactersIn: " .")).lowercased()
        if reserved.contains(stem) { p = "_" + p }
        p = String(p.prefix(120))
        while p.hasSuffix(".") || p.hasSuffix(" ") { p.removeLast() }
        return p.isEmpty ? "_" : p
    }

    nonisolated static func safeRelative(_ path: String, _ size: Int64) -> String? {
        guard path.count <= 600 else { return nil }
        let parts = path.split(whereSeparator: { $0 == "/" || $0 == "\\" }).map(String.init).filter { $0 != "." }
        guard !parts.isEmpty, parts.count <= 6, !parts.contains("..") else { return nil }
        let safe = parts.map { safePart($0) }
        let ext = (safe.last! as NSString).pathExtension.lowercased()
        let limit: Int64 = audio.contains(ext) ? 4 << 30 : (extra[ext] ?? -1)
        guard limit >= 0, size >= 0, size <= limit else { return nil }
        let rel = safe.joined(separator: "/")
        return rel.count <= 200 ? rel : nil
    }

    private nonisolated func handle(_ m: [String: Any]) throws {
        var id: String? = nil
        if let raw = m["id"] {
            guard let s = raw as? String, s.range(of: "^[A-Za-z0-9_-]{1,40}$", options: .regularExpression) != nil
            else { throw PairError.protocolError }
            id = s
        }
        switch m["t"] as? String {
        case "ping": try sendJSON(["t": "pong"])
        case "offer":
            var items: [(String, Int64)] = [], seen = Set<String>()
            let arr = m["items"] as? [[String: Any]] ?? []
            lock.lock(); let reused = id.map { usedIds.contains($0) } ?? true; if let id { usedIds.insert(id) }; lock.unlock()
            let busy = offerOpen
            if !reused, !busy, (1...3000).contains(arr.count) {
                for it in arr {
                    guard let num = it["size"] as? NSNumber, CFGetTypeID(num) != CFBooleanGetTypeID(),
                          case let size = num.int64Value,
                          let rel = PairLink.safeRelative(it["path"] as? String ?? "", size),
                          seen.insert(rel.lowercased()).inserted else { continue }
                    items.append((rel, size))
                }
            }
            if items.isEmpty || items.reduce(0, { $0 + $1.1 }) > 40 << 30 {
                if let id { try sendJSON(["t": "answer", "id": id, "accept": false]) }
                return
            }
            let o = IncomingOffer(id: id!, title: PairLink.cleanName(m["title"] as? String ?? "", ""), items: items)
            offerOpen = true
            Task { @MainActor in self.offer = o }
        case "answer":
            lock.lock(); let cb = id.flatMap { answers.removeValue(forKey: $0) }; lock.unlock()
            cb?(m["accept"] as? Bool == true)
        case "file":
            lock.lock(); defer { lock.unlock() }
            guard let id, let r = receiving[id], !receiving.values.contains(where: { $0.isOpen }) else { throw PairError.protocolError }
            try r.start(m["i"] as? Int ?? -1)
        case "file_end":
            lock.lock(); defer { lock.unlock() }
            guard let id, let r = receiving[id] else { throw PairError.protocolError }
            try r.end(m["i"] as? Int ?? -1, m["sha256"] as? String ?? "")
            let p = "\(r.saved) of \(r.items.count) received"
            Task { @MainActor in self.progress = p }
        case "offer_end":
            lock.lock(); let r = id.flatMap { receiving.removeValue(forKey: $0) }; lock.unlock()
            guard let r else { return }
            r.abort()
            try sendJSON(["t": "received", "id": r.id, "saved": r.saved])
            Task { @MainActor in
                self.progress = ""
                await Library.shared.scan()
            }
        case "cancel":
            lock.lock(); if let id { receiving.removeValue(forKey: id)?.abort() }; let cb = id.flatMap { answers.removeValue(forKey: $0) }; lock.unlock()
            cb?(false)
            Task { @MainActor in if self.offer?.id == id { self.offer = nil } }
        default: break        // a newer version's message
        }
    }

    private nonisolated func onData(_ d: Data) throws {
        lock.lock(); defer { lock.unlock() }
        guard let r = receiving.values.first(where: { $0.isOpen }) else { throw PairError.protocolError }
        try r.data(d)
    }

    /// Your answer to "Receive music?".
    func answer(_ accept: Bool) {
        guard let o = offer else { return }
        offer = nil; offerOpen = false
        var ok = accept
        if ok {
            let free = (try? Library.documents.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey])
                .volumeAvailableCapacityForImportantUsage) ?? 0
            ok = free >= o.total + (200 << 20)
        }
        let folder = PairLink.safePart("From \(computer?.name ?? "computer")")
        if ok { lock.lock(); receiving[o.id] = Receiving(id: o.id, items: o.items, folder: Library.documents.appendingPathComponent(folder)); lock.unlock() }
        Thread { [weak self] in try? self?.sendJSON(["t": "answer", "id": o.id, "accept": ok]) }.start()
    }

    // MARK: sending
    func send(_ tracks: [Track], folder: String = "") {
        let prefix = folder.isEmpty ? "" : PairLink.safePart(folder) + "/"
        var items: [(String, Int64, URL)] = [], seen = Set<String>()
        for t in tracks {
            guard let url = Library.shared.url(for: t),
                  let size = (try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize,
                  let rel = PairLink.safeRelative(prefix + url.lastPathComponent, Int64(size)), seen.insert(rel.lowercased()).inserted
            else { continue }
            items.append((rel, Int64(size), url))
        }
        guard !items.isEmpty else { return }
        let id = (0..<16).map { _ in String("0123456789abcdef".randomElement()!) }.joined()
        let name = computer?.name ?? "your computer"
        progress = "Waiting for \(name) to accept…"
        Thread { [weak self] in
            guard let self else { return }
            let sem = DispatchSemaphore(value: 0); var accepted = false
            self.lock.lock(); self.answers[id] = { ok in accepted = ok; sem.signal() }; self.lock.unlock()
            var ok = false
            do {
                try self.sendJSON(["t": "offer", "id": id, "title": String(folder.prefix(100)),
                                   "items": items.map { ["path": $0.0, "size": $0.1] }])
                if sem.wait(timeout: .now() + 600) == .success, accepted {
                    for (i, item) in items.enumerated() {
                        try self.sendJSON(["t": "file", "id": id, "i": i])
                        var hasher = SHA256(); var sent: Int64 = 0
                        if let h = try? FileHandle(forReadingFrom: item.2) {
                            while sent < item.1, let chunk = try? h.read(upToCount: Int(min(256 * 1024, item.1 - sent))), !chunk.isEmpty {
                                hasher.update(data: chunk); try self.sendData(chunk); sent += Int64(chunk.count)
                            }
                            try? h.close()
                        }
                        try self.sendJSON(["t": "file_end", "id": id, "i": i,
                                           "sha256": hasher.finalize().map { String(format: "%02x", $0) }.joined()])
                    }
                    try self.sendJSON(["t": "offer_end", "id": id])
                    ok = true
                }
            } catch {}
            Task { @MainActor in self.progress = ok ? "Sent to \(name)" : "\(name) didn't take the music" }
        }.start()
    }
}

/// One accepted offer: each file once, checked (size, SHA-256), never more than offered.
private final class Receiving {
    let id: String, items: [(String, Int64)], folder: URL
    let offered: Int64
    var started = Set<Int>(), written: Int64 = 0, saved = 0
    private var index = -1, got: Int64 = 0, tmp: URL?, handle: FileHandle?, hasher = SHA256()
    var isOpen: Bool { index >= 0 }

    init(id: String, items: [(String, Int64)], folder: URL) {
        self.id = id; self.items = items; self.folder = folder; offered = items.reduce(0) { $0 + $1.1 }
    }

    func start(_ i: Int) throws {
        guard items.indices.contains(i), !started.contains(i), !isOpen else { throw PairError.protocolError }
        started.insert(i); index = i; got = 0; hasher = SHA256()
        let t = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".part")
        FileManager.default.createFile(atPath: t.path, contents: nil)
        tmp = t; handle = try? FileHandle(forWritingTo: t)
    }

    func data(_ d: Data) throws {
        got += Int64(d.count); written += Int64(d.count)
        if got > items[index].1 || written > offered { abort(); throw PairError.protocolError }
        hasher.update(data: d)
        do { try handle?.write(contentsOf: d) } catch { try? handle?.close(); handle = nil }
    }

    func end(_ i: Int, _ sha: String) throws {
        guard i == index else { throw PairError.protocolError }
        let (rel, size) = items[i]
        let ok = handle != nil && got == size && hasher.finalize().map { String(format: "%02x", $0) }.joined() == sha
        try? handle?.close()
        if ok, let tmp {
            var target = folder.appendingPathComponent(rel)
            let dir = target.deletingLastPathComponent()
            if dir.standardizedFileURL.path.hasPrefix(folder.standardizedFileURL.path) {
                try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
                var n = 2
                let base = target.deletingPathExtension().lastPathComponent, ext = target.pathExtension
                while FileManager.default.fileExists(atPath: target.path) {
                    target = dir.appendingPathComponent("\(base) (\(n)).\(ext)"); n += 1
                }
                if (try? FileManager.default.moveItem(at: tmp, to: target)) != nil { saved += 1 }
            }
        }
        if let tmp { try? FileManager.default.removeItem(at: tmp) }
        index = -1; handle = nil; tmp = nil
    }

    func abort() {
        try? handle?.close(); if let tmp { try? FileManager.default.removeItem(at: tmp) }
        index = -1; handle = nil; tmp = nil
    }
}

// MARK: - screens

/// Settings → Your computer.
struct PairSettingsSection: View {
    @ObservedObject var link = PairLink.shared
    @State private var scanning = false
    @State private var removing = false

    var body: some View {
        Section {
            if let c = link.computer {
                HStack {
                    VStack(alignment: .leading) {
                        Text(c.name)
                        Text(link.status.isEmpty ? "Not connected" : link.status).font(.caption)
                            .foregroundColor(link.connected ? C.green : C.dim)
                        if !link.progress.isEmpty { Text(link.progress).font(.caption).foregroundColor(C.dim) }
                    }
                    Spacer()
                    Button("Remove", role: .destructive) { removing = true }
                }
            } else if !link.status.isEmpty {
                Text(link.status).font(.caption).foregroundColor(C.dim)
            }
            Button(link.computer == nil ? "Pair with a computer" : "Pair with another computer") { scanning = true }
        } header: { Text("Your computer") } footer: {
            Text("Send songs and folders between this iPhone and Sevbify on your computer. Only on your own Wi-Fi: nothing goes through the internet, everything is encrypted, and you say yes to every transfer. On the computer: Settings → Your phone → Pair a phone. Your iPhone's Camera app can also scan the code. If iOS asks about devices on your local network, choose Allow.")
        }
        .sheet(isPresented: $scanning) {
            QRScanner { text in
                scanning = false
                if let code = PairLink.parse(text) { link.pendingCode = code }
            }
            .ignoresSafeArea()
        }
        .confirmationDialog("Remove \(link.computer?.name ?? "the computer")?", isPresented: $removing, titleVisibility: .visible) {
            Button("Remove", role: .destructive) { link.forget() }
        } message: { Text("This iPhone forgets the computer. To pair again, scan a new code.") }
    }
}

/// "Pair with <computer>?" and "Receive music?" (attached to the app's root view).
struct PairDialogs: ViewModifier {
    @ObservedObject var link = PairLink.shared
    @State private var ready = false

    func body(content: Content) -> some View {
        content
            .alert("Pair with \(link.pendingCode?.name ?? "computer")?", isPresented: Binding(
                get: { link.pendingCode != nil }, set: { if !$0 { link.pendingCode = nil } })) {
                Button("Pair") { if let c = link.pendingCode { link.pair(c) } }
                Button("Cancel", role: .cancel) { link.pendingCode = nil }
            } message: {
                Text("Sevbify on this iPhone and on \(link.pendingCode?.name ?? "the computer") will be able to send each other music, on your Wi-Fi only. You'll be asked before anything is saved.")
            }
            .sheet(item: $link.offer) { offer in
                VStack(alignment: .leading, spacing: 14) {
                    Text("Receive music?").font(.title2.bold())
                    Text("\(link.computer?.name ?? "Your computer") wants to send you \(offer.items.count) file\(offer.items.count == 1 ? "" : "s") (\(String(format: "%.1f", Double(offer.total) / 1_048_576)) MB)\(offer.title.isEmpty ? "" : " — \(offer.title)").")
                    Text(offer.items.prefix(3).map { ($0.0 as NSString).lastPathComponent }.joined(separator: ", ") + (offer.items.count > 3 ? "…" : ""))
                        .foregroundColor(C.dim)
                    Text("They'll be saved in Files → On My iPhone → Sevbify.").font(.caption).foregroundColor(C.dim)
                    HStack {
                        Button("Decline") { link.answer(false) }.buttonStyle(.bordered)
                        Spacer()
                        Button("Accept") { link.answer(true) }.buttonStyle(.borderedProminent).disabled(!ready)
                    }
                }
                .padding(24)
                .presentationDetents([.medium])
                .interactiveDismissDisabled()
                .onAppear { ready = false; DispatchQueue.main.asyncAfter(deadline: .now() + 1) { ready = true } }
            }
            .onOpenURL { url in
                if url.scheme == "sevbify", let code = PairLink.parse(url.absoluteString) { link.pendingCode = code }
            }
    }
}

/// The camera, looking for a QR code (asks for camera access the first time).
struct QRScanner: UIViewControllerRepresentable {
    let found: (String) -> Void
    func makeUIViewController(context: Context) -> ScannerController { ScannerController(found: found) }
    func updateUIViewController(_ vc: ScannerController, context: Context) {}

    final class ScannerController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
        let found: (String) -> Void
        private let session = AVCaptureSession()
        private var done = false
        init(found: @escaping (String) -> Void) { self.found = found; super.init(nibName: nil, bundle: nil) }
        required init?(coder: NSCoder) { fatalError() }

        override func viewDidLoad() {
            super.viewDidLoad()
            view.backgroundColor = .black
            let label = UILabel()
            label.text = "Scan the code on your computer"
            label.textColor = .white
            label.textAlignment = .center
            label.frame = CGRect(x: 0, y: 60, width: view.bounds.width, height: 30)
            label.autoresizingMask = [.flexibleWidth]
            guard let cam = AVCaptureDevice.default(for: .video), let input = try? AVCaptureDeviceInput(device: cam),
                  session.canAddInput(input) else {
                label.text = "No camera available (or access is off in Settings → Sevbify)"
                view.addSubview(label); return
            }
            session.addInput(input)
            let out = AVCaptureMetadataOutput()
            if session.canAddOutput(out) {
                session.addOutput(out)
                out.setMetadataObjectsDelegate(self, queue: .main)
                out.metadataObjectTypes = [.qr]
            }
            let preview = AVCaptureVideoPreviewLayer(session: session)
            preview.frame = view.layer.bounds
            preview.videoGravity = .resizeAspectFill
            view.layer.addSublayer(preview)
            view.addSubview(label)
            DispatchQueue.global(qos: .userInitiated).async { self.session.startRunning() }
        }

        override func viewWillDisappear(_ animated: Bool) {
            super.viewWillDisappear(animated)
            if session.isRunning { session.stopRunning() }
        }

        func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput objects: [AVMetadataObject], from connection: AVCaptureConnection) {
            guard !done, let o = objects.first as? AVMetadataMachineReadableCodeObject, let s = o.stringValue else { return }
            done = true
            session.stopRunning()
            found(s)
        }
    }
}
