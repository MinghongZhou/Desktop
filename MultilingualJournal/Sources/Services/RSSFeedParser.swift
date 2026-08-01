import Foundation

struct RSSItem: Equatable {
    var title: String
    var link: String
    var imageURL: String = ""
}

/// Minimal RSS 2.0 parser built on `XMLParser`. Extracts each `<item>`'s
/// `<title>`, `<link>`, and a representative image (from `media:thumbnail`,
/// `media:content`, or `<enclosure>`). Handles plain text and CDATA-wrapped
/// values. Pure input→output (Data → items), so it's unit-testable without
/// any network.
final class RSSFeedParser: NSObject, XMLParserDelegate {
    static func parse(_ data: Data) -> [RSSItem] {
        let delegate = RSSFeedParser()
        let parser = XMLParser(data: data)
        parser.delegate = delegate
        parser.parse()
        return delegate.items
    }

    private var items: [RSSItem] = []
    private var inItem = false
    private var currentElement = ""
    private var title = ""
    private var link = ""
    private var imageURL = ""

    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName qName: String?, attributes attributeDict: [String: String] = [:]) {
        currentElement = elementName
        let name = (qName ?? elementName).lowercased()

        if elementName == "item" {
            inItem = true
            title = ""
            link = ""
            imageURL = ""
        }

        // Image can live in several namespaced/attribute forms. Take the first
        // image-looking URL we see in an item and keep it.
        guard inItem, imageURL.isEmpty else { return }
        if name.hasSuffix("thumbnail") || name.hasSuffix("media:content") || name == "media:content" {
            if let url = attributeDict["url"], looksLikeImage(url, mediumHint: attributeDict["medium"] ?? attributeDict["type"]) {
                imageURL = url
            }
        } else if name == "enclosure" {
            if let url = attributeDict["url"], looksLikeImage(url, mediumHint: attributeDict["type"]) {
                imageURL = url
            }
        }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        guard inItem else { return }
        switch currentElement {
        case "title": title += string
        case "link": link += string
        default: break
        }
    }

    func parser(_ parser: XMLParser, foundCDATA CDATABlock: Data) {
        guard inItem, let string = String(data: CDATABlock, encoding: .utf8) else { return }
        switch currentElement {
        case "title": title += string
        case "link": link += string
        default: break
        }
    }

    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName qName: String?) {
        if elementName == "item" {
            let cleanTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
            let cleanLink = link.trimmingCharacters(in: .whitespacesAndNewlines)
            if !cleanTitle.isEmpty {
                items.append(RSSItem(title: cleanTitle, link: cleanLink, imageURL: imageURL.trimmingCharacters(in: .whitespacesAndNewlines)))
            }
            inItem = false
        }
        currentElement = ""
    }

    private func looksLikeImage(_ url: String, mediumHint: String?) -> Bool {
        if let hint = mediumHint?.lowercased(), hint.contains("image") { return true }
        let lower = url.lowercased()
        return lower.hasSuffix(".jpg") || lower.hasSuffix(".jpeg") || lower.hasSuffix(".png") || lower.hasSuffix(".webp") || lower.contains("/image")
    }
}
