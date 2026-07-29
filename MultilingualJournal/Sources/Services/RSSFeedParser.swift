import Foundation

struct RSSItem: Equatable {
    var title: String
    var link: String
}

/// Minimal RSS 2.0 parser built on `XMLParser`. Extracts each `<item>`'s
/// `<title>` and `<link>`. Handles both plain text and CDATA-wrapped values
/// (some feeds wrap titles in CDATA). Pure input→output (Data → items), so
/// it's unit-testable without any network.
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

    func parser(_ parser: XMLParser, didStartElement elementName: String, namespaceURI: String?, qualifiedName qName: String?, attributes attributeDict: [String: String] = [:]) {
        currentElement = elementName
        if elementName == "item" {
            inItem = true
            title = ""
            link = ""
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
                items.append(RSSItem(title: cleanTitle, link: cleanLink))
            }
            inItem = false
        }
        currentElement = ""
    }
}
