import Foundation

private let backendName = "swift-coreaudio"

private func makeEncoder() -> JSONEncoder {
    let encoder = JSONEncoder()
    encoder.keyEncodingStrategy = .convertToSnakeCase
    return encoder
}

private final class SignalCoordinator {
    private let semaphore = DispatchSemaphore(value: 0)
    private var sources: [DispatchSourceSignal] = []
    private let handler: () -> Void

    init(handler: @escaping () -> Void) {
        self.handler = handler
    }

    func install() {
        signal(SIGINT, SIG_IGN)
        signal(SIGTERM, SIG_IGN)
        for sig in [SIGINT, SIGTERM] {
            let source = DispatchSource.makeSignalSource(signal: sig, queue: .main)
            source.setEventHandler { [weak self] in
                guard let self else { return }
                self.handler()
                self.semaphore.signal()
            }
            source.resume()
            sources.append(source)
        }
    }

    func wait() {
        semaphore.wait()
    }
}

private func emitFailureAndExit(eventSink: EventSink, message: String, permission: String = "prompt-or-denied") -> Never {
    eventSink.emit(
        HelperEvent(
            event: "error",
            level: "error",
            message: message,
            backend: backendName,
            supported: false,
            permission: permission
        )
    )
    Foundation.exit(1)
}

let eventSink = EventSink(handle: .standardError)

do {
    let configuration = try HelperParser.parse(arguments: CommandLine.arguments)
    guard #available(macOS 14.2, *) else {
        emitFailureAndExit(
            eventSink: eventSink,
            message: "termviz-helper requires macOS 14.2 or newer for Core Audio taps",
            permission: "unsupported"
        )
    }
    let session = AudioCaptureSession(configuration: configuration, eventSink: eventSink)

    switch configuration.mode {
    case .capture:
        do {
            try session.start()
        } catch {
            emitFailureAndExit(eventSink: eventSink, message: String(describing: error))
        }

        eventSink.emit(
            HelperEvent(
                event: "ready",
                level: "info",
                message: "audio capture started",
                backend: backendName,
                supported: true,
                permission: "granted",
                sampleRate: session.actualSampleRate
            )
        )

        let signals = SignalCoordinator {
            session.stop()
        }
        signals.install()
        signals.wait()
        Foundation.exit(0)

    case .check:
        do {
            try session.start()
            session.stop()
            let payload = HelperEvent(
                event: "check",
                message: "audio capture backend is available",
                backend: backendName,
                supported: true,
                permission: "granted",
                sampleRate: session.actualSampleRate
            )
            let encoder = makeEncoder()
            let data = try encoder.encode(payload)
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write(Data([0x0A]))
            Foundation.exit(0)
        } catch {
            let payload = HelperEvent(
                event: "check",
                message: String(describing: error),
                backend: backendName,
                supported: false,
                permission: "prompt-or-denied",
                sampleRate: configuration.sampleRate
            )
            let encoder = makeEncoder()
            let data = try encoder.encode(payload)
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write(Data([0x0A]))
            Foundation.exit(1)
        }
    }
} catch {
    emitFailureAndExit(eventSink: eventSink, message: String(describing: error), permission: "unknown")
}
