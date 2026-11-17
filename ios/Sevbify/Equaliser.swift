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
    /// Volume levelling (songs play at a similar loudness) and Mono audio (both ears get the same sound).
    @Published var level = false { didSet { save() } }
    @Published var mono = false { didSet { save() } }

    private init() {
        if let d = UserDefaults.standard.dictionary(forKey: key) {
            on = d["on"] as? Bool ?? false
            preset = String((d["preset"] as? String ?? "Flat").prefix(40))
            let g = (d["gains"] as? [Double] ?? []).map { Float(max(-12, min(12, $0))) }
            if g.count == 5 { gains = g }
            level = d["level"] as? Bool ?? false
            mono = d["mono"] as? Bool ?? false
        }
        EqualiserTap.update(on: on, gains: gains, level: level, mono: mono)
    }

    private func save() {
        UserDefaults.standard.set(["on": on, "preset": preset, "gains": gains.map { Double($0) }, "level": level, "mono": mono],
                                  forKey: key)
        EqualiserTap.update(on: on, gains: gains, level: level, mono: mono)
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
    private static var extras: (level: Bool, mono: Bool) = (false, false)

    static func update(on: Bool, gains: [Float], level: Bool = false, mono: Bool = false) {
        lock.lock(); current = (on, gains); extras = (level, mono); lock.unlock()
    }

    /// Whether a song needs the tap at all (equaliser, levelling or mono on).
    static var isOn: Bool { lock.lock(); defer { lock.unlock() }; return current.on || extras.level || extras.mono }

    /// Volume levelling: a slow automatic gain towards a steady loudness (about -18 dBFS RMS), limited to
    /// -9…+9 dB and never above full scale, so quiet and loud songs end up close.
    static func level(_ list: UnsafeMutableAudioBufferListPointer, frames: Int, state st: State) {
        guard frames > 0 else { return }
        var sum: Float = 0
        var used = 0
        for buf in list {
            guard let data = buf.mData?.assumingMemoryBound(to: Float.self) else { continue }
            var ms: Float = 0
            vDSP_measqv(data, 1, &ms, vDSP_Length(frames))
            sum += ms; used += 1
        }
        guard used > 0 else { return }
        let rms = sqrt(sum / Float(used))
        if rms > 0.003 {                                      // ignore silence between songs / quiet intros
            st.envelope = st.envelope == 0 ? rms : st.envelope * 0.97 + rms * 0.03
        }
        let target: Float = 0.125
        let want = st.envelope > 0 ? max(0.35, min(2.8, target / st.envelope)) : 1
        st.gain = st.gain * 0.9 + want * 0.1
        var g = st.gain, lo: Float = -1, hi: Float = 1
        for buf in list {
            guard let data = buf.mData?.assumingMemoryBound(to: Float.self) else { continue }
            vDSP_vsmul(data, 1, &g, data, 1, vDSP_Length(frames))
            vDSP_vclip(data, 1, &lo, &hi, data, 1, vDSP_Length(frames))
        }
    }

    /// Mono audio: both channels become their average.
    static func mono(_ list: UnsafeMutableAudioBufferListPointer, frames: Int) {
        guard list.count >= 2, frames > 0,
              let l = list[0].mData?.assumingMemoryBound(to: Float.self),
              let r = list[1].mData?.assumingMemoryBound(to: Float.self) else { return }
        var half: Float = 0.5
        vDSP_vadd(l, 1, r, 1, l, 1, vDSP_Length(frames))
        vDSP_vsmul(l, 1, &half, l, 1, vDSP_Length(frames))
        r.update(from: l, count: frames)
    }

    final class State {
        var sampleRate: Double = 44100
        var channels = 0
        var setups: [vDSP_biquad_Setup] = []
        var delays: [[Float]] = []
        var applied: (on: Bool, gains: [Float]) = (false, [])
        var floatDeinterleaved = false
        var envelope: Float = 0
        var gain: Float = 1

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
                EqualiserTap.lock.lock(); let now = EqualiserTap.current; let ex = EqualiserTap.extras; EqualiserTap.lock.unlock()
                guard st.floatDeinterleaved, st.channels > 0 else { return }
                let list = UnsafeMutableAudioBufferListPointer(buffers)
                let frames = Int(framesOut.pointee)
                if now.on {
                    if now.gains != st.applied.gains || st.setups.count != st.channels {
                        st.rebuild(gains: now.gains)
                        st.applied = now
                    }
                    for (ch, buf) in list.enumerated() where ch < st.setups.count {
                        guard let data = buf.mData?.assumingMemoryBound(to: Float.self) else { continue }
                        st.delays[ch].withUnsafeMutableBufferPointer { d in
                            vDSP_biquad(st.setups[ch], d.baseAddress!, data, 1, data, 1, vDSP_Length(frames))
                        }
                    }
                }
                if ex.mono { EqualiserTap.mono(list, frames: frames) }
                if ex.level { EqualiserTap.level(list, frames: frames, state: st) }
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
        // Mono and levelling on a real two-channel buffer.
        guard let fmt = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 2),
              let pcm = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: 512), let ch = pcm.floatChannelData else { return false }
        pcm.frameLength = 512
        for i in 0..<512 { ch[0][i] = Float(sin(Double(i) * 0.05)) * 0.02; ch[1][i] = 0 }
        let list = UnsafeMutableAudioBufferListPointer(pcm.mutableAudioBufferList)
        mono(list, frames: 512)
        let same = (0..<512).allSatisfy { ch[0][$0] == ch[1][$0] }
        for _ in 0..<50 { level(list, frames: 512, state: st) }
        let louder = (0..<512).map { abs(ch[0][$0]) }.max() ?? 0
        return st.setups.count == 2 && samples.allSatisfy { $0.isFinite } && same && louder > 0.01 && louder <= 1
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
        Section("Sound") {
            Toggle("Volume levelling", isOn: $eq.level).tint(C.green)
            Toggle("Mono audio", isOn: $eq.mono).tint(C.green)
            Text("Volume levelling plays songs at a similar loudness. Mono audio sends the same sound to both ears. Both start from the next song. Left/right balance is in iPhone Settings ▸ Accessibility ▸ Audio & Visual.")
                .font(.caption).foregroundColor(C.dim)
        }
    }
}
