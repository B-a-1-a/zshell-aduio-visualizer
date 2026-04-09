import Foundation
@testable import TermvizHelper
import XCTest

final class TermvizHelperTests: XCTestCase {
    func testParserUsesDefaults() throws {
        let configuration = try HelperParser.parse(arguments: ["termviz-helper", "capture"])
        XCTAssertEqual(configuration, HelperConfiguration(mode: .capture, frameSamples: 1024, sampleRate: 48_000))
    }

    func testParserRejectsUnknownFlag() {
        XCTAssertThrowsError(try HelperParser.parse(arguments: ["termviz-helper", "capture", "--bogus"])) { error in
            XCTAssertTrue(String(describing: error).contains("Unknown argument"))
        }
    }

    func testChunkerEmitsFixedFrames() {
        let chunker = PCMChunker(frameSamples: 4)
        let framesA = chunker.append(samples: [1, 2, 3])
        XCTAssertTrue(framesA.isEmpty)

        let framesB = chunker.append(samples: [4, 5, 6, 7, 8])
        XCTAssertEqual(framesB.count, 2)

        let first = framesB[0].withUnsafeBytes { rawPointer in
            Array(rawPointer.bindMemory(to: Float.self))
        }
        let second = framesB[1].withUnsafeBytes { rawPointer in
            Array(rawPointer.bindMemory(to: Float.self))
        }

        XCTAssertEqual(first, [1, 2, 3, 4])
        XCTAssertEqual(second, [5, 6, 7, 8])
    }

    func testOSStatusFormattingPrefersFourCC() {
        XCTAssertEqual(formatOSStatus(1852797029), "'nope'")
    }
}
