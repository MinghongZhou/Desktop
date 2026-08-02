import Foundation

struct RSSItem: Equatable {
    var title: String
    var link: String
    var imageURL: String = ""
    /// The publisher-provided summary (`<description>`/`<summary>`), HTML
    /// stripped and length-capped. This is the syndication snippet, not the
    /// full article body — feeds only carry a short summary, and the app
    /// deliberately links out for the rest rather than reproducing articles.
    var summary: String = ""
}

/// Minimal RSS 2.0 parser built on `XMLParser`. Extracts each `<item>`'s
/// `<title>`, `<link>`, `<description>` summary, and a representative image
/// (from `media:thumbnail`, `media:content`, or `<enclosure>`). Handles plain
/// text and CDATA-wrapped values. Pure input→output (Data → items), so it's
/// unit-testable without any network.
final class RSSFeedParser: NSObject, XMLParserDelegate {
    /// Cap so we keep a summary snippet, never a near-full-article dump.
    private static let summaryCharLimit = 400
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
    private var summary = ""

    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName qName: String?, attributes attributeDict: [String: String] = [:]) {
        currentElement = elementName
        let name = (qName ?? elementName).lowercased()

        if elementName == "item" {
            inItem = true
            title = ""
            link = ""
            imageURL = ""
            summary = ""
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
        accumulate(string)
    }

    func parser(_ parser: XMLParser, foundCDATA CDATABlock: Data) {
        guard inItem, let string = String(data: CDATABlock, encoding: .utf8) else { return }
        accumulate(string)
    }

    private func accumulate(_ string: String) {
        switch currentElement {
        case "title": title += string
        case "link": link += string
        // "summary" covers Atom feeds; "description" covers RSS 2.0.
        case "description", "summary": summary += string
        default: break
        }
    }

    func parser(_ parser: XMLParser, didEndElement elementName: String, namespaceURI: String?, qualifiedName qName: String?) {
        if elementName == "item" {
            let cleanTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
            let cleanLink = link.trimmingCharacters(in: .whitespacesAndNewlines)
            var cleanSummary = Self.plainText(summary)
            // Drop a summary that just repeats the headline — no added detail.
            if cleanSummary == cleanTitle { cleanSummary = "" }
            if !cleanTitle.isEmpty {
                items.append(RSSItem(
                    title: cleanTitle,
                    link: cleanLink,
                    imageURL: imageURL.trimmingCharacters(in: .whitespacesAndNewlines),
                    summary: cleanSummary
                ))
            }
            inItem = false
        }
        currentElement = ""
    }

    /// Strips HTML tags, decodes common entities, collapses whitespace, and
    /// caps the length — turning a feed's `<description>` HTML into a plain,
    /// display-ready snippet.
    static func plainText(_ raw: String) -> String {
        var s = raw.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        let entities = [
            "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"",
            "&#39;": "'", "&apos;": "'", "&nbsp;": " ", "&#160;": " ",
        ]
        for (entity, value) in entities {
            s = s.replacingOccurrences(of: entity, with: value)
        }
        s = s.replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if s.count > summaryCharLimit {
            let end = s.index(s.startIndex, offsetBy: summaryCharLimit)
            s = s[..<end].trimmingCharacters(in: .whitespacesAndNewlines) + "…"
        }
        return s
    }

    private func looksLikeImage(_ url: String, mediumHint: String?) -> Bool {
        if let hint = mediumHint?.lowercased(), hint.contains("image") { return true }
        let lower = url.lowercased()
        return lower.hasSuffix(".jpg") || lower.hasSuffix(".jpeg") || lower.hasSuffix(".png") || lower.hasSuffix(".webp") || lower.contains("/image")
    }
}
