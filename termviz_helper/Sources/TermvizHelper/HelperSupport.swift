import Foundation

public enum HelperMode: String, Equatable {
    case capture
    case check
}

public struct HelperConfiguration: Equatable {
    public let mode: HelperMode
    public let frameSamples: Int
    public let sampleRate: Int

    public init(mode: HelperMode, frameSamples: Int, sampleRate: Int) {
        self.mode = mode
        self.frameSamples = frameSamples
        self.sampleRate = sampleRate
    }
}

public struct HelperEvent: Codable, Equatable {
    public let event: String
    public let level: String?
    public let message: String
    public let backend: String?
    public let supported: Bool?
    public let permission: String?
    public let sampleRate: Int?

    public init(
        event: String,
        level: String? = nil,
        message: String,
        backend: String? = nil,
        supported: Bool? = nil,
        permission: String? = nil,
        sampleRate: Int? = nil
    ) {
        self.event = event
        self.level = level
        self.message = message
        self.backend = backend
        self.supported = supported
        self.permission = permission
        self.sampleRate = sampleRate
    }
}

public enum HelperRuntimeError: Error, Equatable, CustomStringConvertible {
    case usage(String)
    case coreAudio(operation: String, status: Int32)
    case unsupportedFormat(String)
    case io(String)

    public var description: String {
        switch self {
        case .usage(let message):
            return message
        case .coreAudio(let operation, let status):
            return "\(operation) failed with OSStatus \(formatOSStatus(status))"
        case .unsupportedFormat(let description):
            return "Unsupported audio format: \(description)"
        case .io(let message):
            return message
        }
    }
}

public enum HelperParser {
    public static func parse(arguments: [String]) throws -> HelperConfiguration {
        var args = Array(arguments.dropFirst())
        guard let subcommand = args.first, let mode = HelperMode(rawValue: subcommand) else {
            throw HelperRuntimeError.usage("Usage: termviz-helper <capture|check> [--frame-samples N] [--sample-rate N]")
        }
        args.removeFirst()

        var frameSamples = 1024
        var sampleRate = 48_000

        while let arg = args.first {
            args.removeFirst()
            switch arg {
            case "--frame-samples":
                guard let value = args.first, let parsed = Int(value), parsed > 0 else {
                    throw HelperRuntimeError.usage("--frame-samples requires a positive integer")
                }
                frameSamples = parsed
                args.removeFirst()
            case "--sample-rate":
                guard let value = args.first, let parsed = Int(value), parsed > 0 else {
                    throw HelperRuntimeError.usage("--sample-rate requires a positive integer")
                }
                sampleRate = parsed
                args.removeFirst()
            default:
                throw HelperRuntimeError.usage("Unknown argument: \(arg)")
            }
        }

        return HelperConfiguration(mode: mode, frameSamples: frameSamples, sampleRate: sampleRate)
    }
}

public final class PCMChunker {
    public let frameSamples: Int
    private var pending: [Float]

    public init(frameSamples: Int) {
        self.frameSamples = frameSamples
        self.pending = []
        self.pending.reserveCapacity(frameSamples * 2)
    }

    public func append(samples: [Float]) -> [Data] {
        pending.append(contentsOf: samples)
        var frames: [Data] = []
        while pending.count >= frameSamples {
            let frame = Array(pending.prefix(frameSamples))
            pending.removeFirst(frameSamples)
            frames.append(frame.withUnsafeBufferPointer { pointer in
                Data(buffer: pointer)
            })
        }
        return frames
    }
}

public final class EventSink {
    private let encoder = JSONEncoder()
    private let handle: FileHandle
    private let lock = NSLock()

    public init(handle: FileHandle) {
        encoder.keyEncodingStrategy = .convertToSnakeCase
        self.handle = handle
    }

    public func emit(_ event: HelperEvent) {
        lock.lock()
        defer { lock.unlock() }
        do {
            let data = try encoder.encode(event)
            handle.write(data)
            handle.write(Data([0x0A]))
        } catch {
            let fallback = "{\"event\":\"error\",\"message\":\"failed to encode helper event\"}\n"
            handle.write(Data(fallback.utf8))
        }
    }
}

public func formatOSStatus(_ status: Int32) -> String {
    let bigEndian = UInt32(bitPattern: status)
    let bytes = [
        UInt8((bigEndian >> 24) & 0xff),
        UInt8((bigEndian >> 16) & 0xff),
        UInt8((bigEndian >> 8) & 0xff),
        UInt8(bigEndian & 0xff),
    ]
    let printable = bytes.allSatisfy { 32...126 ~= $0 }
    if printable {
        return "'\(String(bytes: bytes, encoding: .ascii) ?? "????")'"
    }
    return String(status)
}
