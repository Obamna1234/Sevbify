import SwiftUI

/// iPhone updates: the app is installed with AltStore / SideStore, which install new versions themselves once
/// Sevbify's source is added (it's updated with every release). Once a day Sevbify checks GitHub and offers a new
/// version once, with buttons that open AltStore / SideStore (or the release page).
@MainActor
final class AppUpdates: ObservableObject {
    static let shared = AppUpdates()
    static let source = "https://raw.githubusercontent.com/Obamna1234/Sevbify/altstore/source.json"
    @Published var offer: (latest: String, page: String)?
    @Published var showing = false

    var version: String { Bundle.main.object(forInfoDictionaryKey: "SevbifyVersion") as? String ?? "" }

    @discardableResult
    func check(manual: Bool = false) async -> String {
        let lib = Library.shared
        guard lib.settings.online else { return "Turn on Online features to check for updates." }
        if !manual && Date().timeIntervalSince1970 - lib.settings.lastAppCheck < 24 * 3600 { return "" }
        guard let r = try? await Bridge.object("check_updates", [version, "ios"]) else {
            return "Couldn't reach GitHub. Try again later."
        }
        lib.settings.lastAppCheck = Date().timeIntervalSince1970
        if r["newer"] as? Bool == true, let latest = r["latest"] as? String {
            if manual || lib.settings.updateAsked != latest {
                lib.settings.updateAsked = latest
                offer = (latest, r["page"] as? String ?? "https://github.com/Obamna1234/Sevbify/releases")
                showing = true
            }
        }
        lib.save()
        return r["message"] as? String ?? ""
    }

    /// Adds Sevbify's source to AltStore / SideStore (they then update Sevbify like an App Store app).
    func openStore(_ scheme: String) {
        let encoded = AppUpdates.source.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? ""
        if let url = URL(string: "\(scheme)://source?url=\(encoded)") { UIApplication.shared.open(url) }
    }
}

@MainActor
struct UpdateAlert: ViewModifier {
    @ObservedObject var updates = AppUpdates.shared

    func body(content: Content) -> some View {
        content.alert("Update Sevbify", isPresented: $updates.showing, presenting: updates.offer) { o in
            Button("Open SideStore") { updates.openStore("sidestore") }
            Button("Open AltStore") { updates.openStore("altstore") }
            Button("Release page") {
                let page = isSevbifyPage(o.page) ? o.page : "https://github.com/Obamna1234/Sevbify/releases"
                if let u = URL(string: page) { UIApplication.shared.open(u) }
            }
            Button("Later", role: .cancel) {}
        } message: { o in
            Text("Sevbify \(o.latest) is available (you have \(updates.version)). Update it in SideStore or AltStore: your playlists, downloads and settings stay.")
        }
    }
}
