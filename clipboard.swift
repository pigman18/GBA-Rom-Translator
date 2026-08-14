import AppKit

guard CommandLine.arguments.count > 1 else {
    fputs("usage: swift clipboard.swift <output.png>\n", stderr)
    exit(2)
}

let outputPath = CommandLine.arguments[1]
let pasteboard = NSPasteboard.general

func writePng(from data: Data) -> Bool {
    guard let rep = NSBitmapImageRep(data: data),
          let png = rep.representation(using: .png, properties: [:]) else {
        return false
    }
    do {
        try png.write(to: URL(fileURLWithPath: outputPath))
        return true
    } catch {
        return false
    }
}

if let pngData = pasteboard.data(forType: .png), writePng(from: pngData) {
    exit(0)
}
if let tiffData = pasteboard.data(forType: .tiff), writePng(from: tiffData) {
    exit(0)
}

fputs("no image found in clipboard\n", stderr)
exit(1)
