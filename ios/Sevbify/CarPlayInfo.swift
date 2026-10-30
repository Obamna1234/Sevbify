import SwiftUI
import AVFoundation

/// CarPlay: Sevbify's music plays through CarPlay (controls and the song on its Now Playing screen), but a sideloaded
/// app can't have its own CarPlay icon: Apple only allows that for App Store apps with its permission. The first time
/// the iPhone plays through CarPlay, Sevbify says so once, so nobody waits for an icon that won't come.
@MainActor
final class CarPlayInfo: ObservableObject {
    static let shared = CarPlayInfo()
    @Published var showing = false
    private var watching = false
    private let key = "carPlayInfoShown"

    func watch() {
        guard !watching else { return }
        watching = true
        NotificationCenter.default.addObserver(forName: AVAudioSession.routeChangeNotification, object: nil, queue: .main) { _ in
            Task { @MainActor in CarPlayInfo.shared.check() }
        }
        check()
    }

    func check() {
        let car = AVAudioSession.sharedInstance().currentRoute.outputs.contains { $0.portType == .carAudio }
        if car && !UserDefaults.standard.bool(forKey: key) {
            UserDefaults.standard.set(true, forKey: key)
            showing = true
        }
    }

    static let text = "Sevbify plays through CarPlay: the song, play / pause and skip are on CarPlay's Now Playing screen and the steering-wheel buttons. Sevbify can't have its own icon on the CarPlay screen, because Apple only allows that for App Store apps. Bluetooth in any car works too."
}

@MainActor
struct CarPlayAlert: ViewModifier {
    @ObservedObject var info = CarPlayInfo.shared
    func body(content: Content) -> some View {
        content
            .onAppear { info.watch() }
            .alert("Sevbify in your car", isPresented: $info.showing) { Button("OK", role: .cancel) {} } message: {
                Text(CarPlayInfo.text)
            }
    }
}
