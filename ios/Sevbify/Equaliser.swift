import AVFoundation
import Accelerate
import MediaToolbox
import SwiftUI

/// The equaliser on iPhone, like the PC's and Android's: a 5-band equaliser applied to the sound as it plays, on the
/// phone (nothing leaves it). Settings → Playback → Equaliser: on/off, presets, or Custom with a slider per band.
/// It works through an audio "tap" on the playing song; for the rare stream type that doesn't allow one, the song
/// simply plays without it.
final class EqualiserSettings: ObservableObject {
    static let shared = EqualiserSettings()
    static let frequencies: [Double] = [60, 230, 910, 3600, 14000]
    static let labels = ["60 Hz", "230 Hz", "910 Hz", "3.6 kHz", "14 kHz"]
    static let presets: [(String, [Float])] = [
        ("Flat", [0, 0, 0, 0, 0]), ("Bass boost", [6, 4, 0, 0, 0]), ("Vocal", [-2, 0, 3, 4, 1]),
        ("Rock", [4, 2, -2, 2, 4]), ("Pop", [-1, 2, 4, 2, -1]), ("Acoustic", [3, 1, 1, 2, 2]),
        ("Classical", [3, 2, -1, 2, 3]), ("Treble boost", [0, 0, 0, 3, 6]),
    ]
    private let key = "sevbify.eq"
    @Published var on = false { didSet { save() } }
    @Published var preset = "Flat" { didSet { save() } }
    @Published var gains: [Float] = [0, 0, 0, 0, 0] { didSet { save() } }

    private init() {
        if let d = UserDefaults.standard.dictionary(forKey: key) {
            on = d["on"] as? Bool ?? false
            preset = String((d["preset"] as? String ?? "Flat").prefix(40))
            let g = (d["gains"] as? [Double] ?? []).map { Float(max(-12, min(12, $0))) }
            if g.count == 5 { gains = g }
        }
        EqualiserTap.update(on: on, gains: gains)
    }

    private func save() {
        UserDefaults.standard.set(["on": on, "preset": preset, "gains": gains.map { Double($0) }], forKey: key)
        EqualiserTap.update(on: on, gains: gains)
    }

    func choose(_ name: String) {
        preset = name
        if let p = Self.presets.first(where: { $0.0 == name }) { gains = p.1 }
    }
}

/// The processing behind it: peaking filters (RBJ cookbook) run with Accelerate's vDSP biquads, per channel.
final class EqualiserTap {
    private static let lock = NSLock()
    private static var current: (on: Bool, gains: [Float]) = (false, [0, 0, 0, 0, 0])

    static func update(on: Bool, gains: [Float]) {
        lock.lock(); current = (on, gains); lock.unlock()
    }

    static var isOn: Bool { lock.lock(); defer { lock.unlock() }; return current.on }

    final class State {
        var sampleRate: Double = 44100
        var channels = 0
        var setups: [vDSP_biquad_Setup] = []
        var delays: [[Float]] = []
        var applied: (on: Bool, gains: [Float]) = (false, [])
        var floatDeinterleaved = false

        func rebuild(gains: [Float]) {
            for s in setups { vDSP_biquad_DestroySetup(s) }
            setups = []
            var coeffs: [Double] = []
            for (i, f) in EqualiserSettings.frequencies.enumerated() {
                let gain = Double(i < gains.count ? gains[i] : 0)
                let a = pow(10, gain / 40), w = 2 * Double.pi * min(f, sampleRate * 0.45) / sampleRate
                let alpha = sin(w) / (2 * 1.0)                    // Q = 1
                let b0 = 1 + alpha * a, b1 = -2 * cos(w), b2 = 1 - alpha * a
                let a0 = 1 + alpha / a, a1 = -2 * cos(w), a2 = 1 - alpha / a
                coeffs += [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0]
            }
            for _ in 0..<channels {
                if let s = vDSP_biquad_CreateSetup(coeffs, vDSP_Length(EqualiserSettings.frequencies.count)) { setups.append(s) }
            }
            delays = Array(repeating: Array(repeating: 0, count: 2 * EqualiserSettings.frequencies.count + 2), count: channels)
        }

        deinit { for s in setups { vDSP_biquad_DestroySetup(s) } }
    }

    /// An audio mix that runs the equaliser on this asset's first audio track (nil if it can't).
    static func audioMix(for asset: AVAsset) async -> AVAudioMix? {
        guard let track = try? await asset.loadTracks(withMediaType: .audio).first else { return nil }
        let state = State()
        var callbacks = MTAudioProcessingTapCallbacks(
            version: kMTAudioProcessingTapCallbacksVersion_0,
            clientInfo: UnsafeMutableRawPointer(Unmanaged.passRetained(state).toOpaque()),
            init: { _, clientInfo, storageOut in storageOut.pointee = clientInfo },
            finalize: { tap in
                Unmanaged<State>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).release()
            },
            prepare: { tap, _, format in
                let st = Unmanaged<State>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue()
                let f = format.pointee
                st.sampleRate = f.mSampleRate > 0 ? f.mSampleRate : 44100
                st.channels = Int(f.mChannelsPerFrame)
                st.floatDeinterleaved = (f.mFormatFlags & kAudioFormatFlagIsFloat) != 0
                    && (f.mFormatFlags & kAudioFormatFlagIsNonInterleaved) != 0 && f.mBitsPerChannel == 32
                st.applied = (false, [])
            },
            unprepare: nil,
            process: { tap, frames, _, buffers, framesOut, flagsOut in
                guard MTAudioProcessingTapGetSourceAudio(tap, frames, buffers, flagsOut, nil, framesOut) == noErr else { return }
                let st = Unmanaged<State>.fromOpaque(MTAudioProcessingTapGetStorage(tap)).takeUnretainedValue()
                EqualiserTap.lock.lock(); let now = EqualiserTap.current; EqualiserTap.lock.unlock()
                guard now.on, st.floatDeinterleaved, st.channels > 0 else { return }
                if now.gains != st.applied.gains || st.setups.count != st.channels {
                    st.rebuild(gains: now.gains)
                    st.applied = now
                }
                let list = UnsafeMutableAudioBufferListPointer(buffers)
                for (ch, buf) in list.enumerated() where ch < st.setups.count {
                    guard let data = buf.mData?.assumingMemoryBound(to: Float.self) else { continue }
                    let n = vDSP_Length(framesOut.pointee)
                    st.delays[ch].withUnsafeMutableBufferPointer { d in
                        vDSP_biquad(st.setups[ch], d.baseAddress!, data, 1, data, 1, n)
                    }
                }
            })
        var tap: MTAudioProcessingTap?
        guard MTAudioProcessingTapCreate(kCFAllocatorDefault, &callbacks, kMTAudioProcessingTapCreationFlag_PostEffects, &tap) == noErr,
              let made = tap else {
            Unmanaged<State>.fromOpaque(callbacks.clientInfo!).release()
            return nil
        }
        let params = AVMutableAudioMixInputParameters(track: track)
        params.audioTapProcessor = made
        let mix = AVMutableAudioMix()
        mix.inputParameters = [params]
        return mix
    }

    /// Self-test for the automatic iPhone check: the filters can be built and run without crashing.
    static func selfTest() -> Bool {
        let st = State()
        st.channels = 2
        st.rebuild(gains: [6, 0, -3, 0, 3])
        var samples = (0..<512).map { Float(sin(Double($0) * 0.1)) }
        st.delays[0].withUnsafeMutableBufferPointer { d in
            samples.withUnsafeMutableBufferPointer { s in
                vDSP_biquad(st.setups[0], d.baseAddress!, s.baseAddress!, 1, s.baseAddress!, 1, 512)
            }
        }
        return st.setups.count == 2 && samples.allSatisfy { $0.isFinite }
    }
}

struct EqualiserSection: View {
    @ObservedObject var eq = EqualiserSettings.shared
    var body: some View {
        Section("Equaliser") {
            Toggle("Equaliser", isOn: $eq.on).tint(C.green)
            if eq.on {
                Picker("Preset", selection: Binding(get: { eq.preset }, set: { eq.choose($0) })) {
                    ForEach(EqualiserSettings.presets.map { $0.0 } + ["Custom"], id: \.self) { Text($0) }
                }
                ForEach(0..<5, id: \.self) { i in
                    HStack {
                        Text(EqualiserSettings.labels[i]).font(.caption).frame(width: 60, alignment: .leading)
                        Slider(value: Binding(get: { Double(eq.gains[i]) },
                                              set: { v in var g = eq.gains; g[i] = Float(v); eq.gains = g; eq.preset = "Custom" }),
                               in: -12...12, step: 1).tint(C.green)
                        Text("\(Int(eq.gains[i])) dB").font(.caption).frame(width: 44)
                    }
                }
            }
            Text("Shapes the sound on this iPhone. Turning it on or off takes effect from the next song; preset and slider changes apply straight away.")
                .font(.caption).foregroundColor(C.dim)
        }
    }
}
