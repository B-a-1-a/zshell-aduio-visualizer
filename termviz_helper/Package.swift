// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "termviz-helper",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(name: "termviz-helper", targets: ["TermvizHelper"]),
    ],
    targets: [
        .executableTarget(
            name: "TermvizHelper"
        ),
        .testTarget(
            name: "TermvizHelperTests",
            dependencies: ["TermvizHelper"]
        ),
    ]
)
