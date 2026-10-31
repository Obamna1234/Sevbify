import Foundation

/// Calls Sevbify's shared Python code (core/, through ios_entry.py). Same functions as the Android app's bridge.
/// Every call runs off the main thread; results come back as JSON values.
enum Bridge {
    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    private static let queue = DispatchQueue(label: "sevbify.python", qos: .userInitiated, attributes: .concurrent)
    private(set) static var startError: String? = nil
    private static var started = false
    private static let startLock = NSLock()

    /// Starts Python (once). Safe to call from any thread.
    static func start() -> Bool {
        startLock.lock(); defer { startLock.unlock() }
        if started { return true }
        let resources = Bundle.main.resourcePath ?? ""
        var buffer = [CChar](repeating: 0, count: 512)
        let code = sev_py_start(resources, &buffer, Int32(buffer.count))
        if code != 0 {
            startError = "Python didn't start (\(code)): " + String(cString: buffer)
            NSLog("Sevbify: %@", startError ?? "")
            return false
        }
        started = true
        return true
    }

    /// Runs a bridge function and returns its "value" (Any), or throws with a readable message.
    static func call(_ name: String, _ args: [Any] = []) async throws -> Any {
        try await withCheckedThrowingContinuation { cont in
            queue.async {
                do { cont.resume(returning: try callSync(name, args)) } catch { cont.resume(throwing: error) }
            }
        }
    }

    // Pages may ask for things (genres, search...) before start-up has told Python where its data lives;
    // those calls wait for markReady() (at most 60 s) instead of failing.
    private static let ready = NSCondition()
    private static var isReady = false
    private static let beforeSetup: Set<String> = ["setup", "set_online", "set_source", "python_info", "scan_folder",
                                                   "read_tags", "cover_art"]

    static func markReady() {
        ready.lock(); isReady = true; ready.broadcast(); ready.unlock()
    }

    static func callSync(_ name: String, _ args: [Any] = []) throws -> Any {
        guard start() else { throw Failure(message: startError ?? "Python didn't start") }
        if !beforeSetup.contains(name) {
            ready.lock()
            let deadline = Date().addingTimeInterval(60)
            while !isReady && ready.wait(until: deadline) {}
            ready.unlock()
        }
        let data = try JSONSerialization.data(withJSONObject: args.map(jsonSafe), options: [])
        let argText = String(data: data, encoding: .utf8) ?? "[]"
        guard let raw = sev_py_call(name, argText) else { throw Failure(message: "No answer from Python") }
        let text = String(cString: raw)
        free(raw)
        guard let obj = try JSONSerialization.jsonObject(with: Data(text.utf8), options: [.fragmentsAllowed]) as? [String: Any]
        else { throw Failure(message: "Unreadable answer from Python") }
        if obj["ok"] as? Bool == true { return obj["value"] ?? NSNull() }
        let msg = obj["error"] as? String ?? "Something went wrong"
        #if DEBUG   // test builds only: errors can hold song names or addresses
        if let trace = obj["trace"] as? String { NSLog("Sevbify %@ failed: %@\n%@", name, msg, trace) }
        #endif
        throw Failure(message: msg)
    }

    private static func jsonSafe(_ v: Any) -> Any {
        switch v {
        case let t as Track: return t.dict
        case let ts as [Track]: return ts.map { $0.dict }
        default: return v
        }
    }

    // --- typed helpers -----------------------------------------------------------------------------------
    static func tracks(_ name: String, _ args: [Any] = []) async throws -> [Track] {
        let v = try await call(name, args)
        return (v as? [[String: Any]] ?? []).map(Track.init(dict:))
    }

    static func object(_ name: String, _ args: [Any] = []) async throws -> [String: Any] {
        try await call(name, args) as? [String: Any] ?? [:]
    }

    static func list(_ name: String, _ args: [Any] = []) async throws -> [[String: Any]] {
        try await call(name, args) as? [[String: Any]] ?? []
    }

    /// JSON text for one value (bridge functions that take a JSON string, e.g. album_tracks).
    static func json(_ value: Any) -> String {
        guard let d = try? JSONSerialization.data(withJSONObject: value, options: []) else { return "{}" }
        return String(data: d, encoding: .utf8) ?? "{}"
    }
}
