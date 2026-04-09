import AudioToolbox
import CoreAudio
import Foundation

@available(macOS 14.2, *)
final class AudioCaptureSession {
    private let configuration: HelperConfiguration
    private let chunker: PCMChunker
    private let writerLock = NSLock()

    private var tapID: AudioObjectID = 0
    private var aggregateDeviceID: AudioObjectID = 0
    private var ioProcID: AudioDeviceIOProcID?
    private var tapDescription: CATapDescription?
    private var inputFormat = AudioStreamBasicDescription()
    private var isRunning = false

    init(configuration: HelperConfiguration, eventSink: EventSink) {
        self.configuration = configuration
        self.chunker = PCMChunker(frameSamples: configuration.frameSamples)
    }

    var actualSampleRate: Int {
        Int(inputFormat.mSampleRate.rounded())
    }

    func start() throws {
        guard !isRunning else { return }
        let tapUUID = UUID()
        let description = CATapDescription(monoGlobalTapButExcludeProcesses: [])
        description.name = "termviz system audio tap"
        description.uuid = tapUUID
        description.isPrivate = true
        description.muteBehavior = .unmuted
        tapDescription = description

        try check(AudioHardwareCreateProcessTap(description, &tapID), operation: "AudioHardwareCreateProcessTap")

        let aggregateUID = "io.termviz.aggregate.\(UUID().uuidString)"
        let tapList: [[String: Any]] = [[
            kAudioSubTapUIDKey: tapUUID.uuidString,
            kAudioSubTapDriftCompensationKey: 1,
            kAudioSubTapDriftCompensationQualityKey: Int(kAudioAggregateDriftCompensationMaxQuality),
        ]]
        let aggregateDescription: [String: Any] = [
            kAudioAggregateDeviceNameKey: "termviz aggregate device",
            kAudioAggregateDeviceUIDKey: aggregateUID,
            kAudioAggregateDeviceIsPrivateKey: 1,
            kAudioAggregateDeviceTapListKey: tapList,
        ]

        do {
            try check(
                AudioHardwareCreateAggregateDevice(aggregateDescription as CFDictionary, &aggregateDeviceID),
                operation: "AudioHardwareCreateAggregateDevice"
            )
            try configureDevice()
            try installIOProc()
            try check(AudioDeviceStart(aggregateDeviceID, ioProcID), operation: "AudioDeviceStart")
            inputFormat = try tapFormat()
            isRunning = true
        } catch {
            stop()
            throw error
        }
    }

    func stop() {
        if aggregateDeviceID != 0, let ioProcID {
            _ = AudioDeviceStop(aggregateDeviceID, ioProcID)
            _ = AudioDeviceDestroyIOProcID(aggregateDeviceID, ioProcID)
            self.ioProcID = nil
        }
        if aggregateDeviceID != 0 {
            _ = AudioHardwareDestroyAggregateDevice(aggregateDeviceID)
            aggregateDeviceID = 0
        }
        if tapID != 0 {
            _ = AudioHardwareDestroyProcessTap(tapID)
            tapID = 0
        }
        isRunning = false
    }

    private func installIOProc() throws {
        var createdProc: AudioDeviceIOProcID?
        let status = AudioDeviceCreateIOProcIDWithBlock(&createdProc, aggregateDeviceID, nil) { [weak self] _, inputData, _, _, _ in
            guard let self else { return }
            self.handleAudioBufferList(inputData)
        }
        try check(status, operation: "AudioDeviceCreateIOProcIDWithBlock")
        ioProcID = createdProc
    }

    private func configureDevice() throws {
        var sampleRate = Float64(configuration.sampleRate)
        try setDeviceProperty(
            selector: kAudioDevicePropertyNominalSampleRate,
            pointer: &sampleRate,
            valueSize: UInt32(MemoryLayout.size(ofValue: sampleRate))
        )

        var frameSamples = UInt32(configuration.frameSamples)
        try setDeviceProperty(
            selector: kAudioDevicePropertyBufferFrameSize,
            pointer: &frameSamples,
            valueSize: UInt32(MemoryLayout.size(ofValue: frameSamples))
        )
    }

    private func setDeviceProperty<T>(
        selector: AudioObjectPropertySelector,
        pointer: inout T,
        valueSize: UInt32
    ) throws {
        var address = AudioObjectPropertyAddress(
            mSelector: selector,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        let status = withUnsafePointer(to: &pointer) { rawPointer in
            AudioObjectSetPropertyData(
                aggregateDeviceID,
                &address,
                0,
                nil,
                valueSize,
                rawPointer
            )
        }
        if status != kAudioHardwareNoError {
            throw HelperRuntimeError.coreAudio(operation: "AudioObjectSetPropertyData(\(selector))", status: status)
        }
    }

    private func tapFormat() throws -> AudioStreamBasicDescription {
        var address = AudioObjectPropertyAddress(
            mSelector: kAudioTapPropertyFormat,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        var format = AudioStreamBasicDescription()
        var dataSize = UInt32(MemoryLayout.size(ofValue: format))
        try check(
            AudioObjectGetPropertyData(tapID, &address, 0, nil, &dataSize, &format),
            operation: "AudioObjectGetPropertyData(kAudioTapPropertyFormat)"
        )
        guard format.mFormatID == kAudioFormatLinearPCM else {
            throw HelperRuntimeError.unsupportedFormat("formatID=\(format.mFormatID)")
        }
        guard format.mBitsPerChannel == 32, format.mFormatFlags & kAudioFormatFlagIsFloat != 0 else {
            throw HelperRuntimeError.unsupportedFormat("expected float32 PCM")
        }
        return format
    }

    private func handleAudioBufferList(_ inputData: UnsafePointer<AudioBufferList>) {
        let monoSamples = decodeMonoSamples(from: inputData)
        guard !monoSamples.isEmpty else { return }
        let frames = chunker.append(samples: monoSamples)
        writerLock.lock()
        defer { writerLock.unlock() }
        for frame in frames {
            FileHandle.standardOutput.write(frame)
        }
    }

    private func decodeMonoSamples(from inputData: UnsafePointer<AudioBufferList>) -> [Float] {
        let buffers = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: inputData))
        guard !buffers.isEmpty else { return [] }

        let isNonInterleaved = inputFormat.mFormatFlags & kAudioFormatFlagIsNonInterleaved != 0
        let declaredChannels = max(1, Int(inputFormat.mChannelsPerFrame))

        if buffers.count == 1 && !isNonInterleaved {
            let buffer = buffers[0]
            guard let base = buffer.mData else { return [] }
            let sampleCount = Int(buffer.mDataByteSize) / MemoryLayout<Float>.size
            let pointer = base.bindMemory(to: Float.self, capacity: sampleCount)
            let samples = UnsafeBufferPointer(start: pointer, count: sampleCount)
            if declaredChannels == 1 {
                return Array(samples)
            }
            var output = Array(repeating: Float(0), count: sampleCount / declaredChannels)
            for frameIndex in output.indices {
                var sum: Float = 0
                for channel in 0..<declaredChannels {
                    sum += samples[frameIndex * declaredChannels + channel]
                }
                output[frameIndex] = sum / Float(declaredChannels)
            }
            return output
        }

        let frameCount = buffers.reduce(Int.max) { current, buffer in
            let samples = Int(buffer.mDataByteSize) / MemoryLayout<Float>.size
            return min(current, samples)
        }
        guard frameCount > 0, frameCount != Int.max else { return [] }

        var output = Array(repeating: Float(0), count: frameCount)
        for buffer in buffers {
            guard let base = buffer.mData else { continue }
            let pointer = base.bindMemory(to: Float.self, capacity: frameCount)
            let samples = UnsafeBufferPointer(start: pointer, count: frameCount)
            for index in 0..<frameCount {
                output[index] += samples[index]
            }
        }
        let divisor = Float(max(1, buffers.count))
        for index in output.indices {
            output[index] /= divisor
        }
        return output
    }

    private func check(_ status: OSStatus, operation: String) throws {
        if status != kAudioHardwareNoError {
            throw HelperRuntimeError.coreAudio(operation: operation, status: status)
        }
    }
}
