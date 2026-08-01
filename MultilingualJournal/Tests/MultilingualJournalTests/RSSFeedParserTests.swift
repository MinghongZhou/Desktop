import XCTest
@testable import MultilingualJournal

final class RSSFeedParserTests: XCTestCase {
    func testParsesTitlesAndLinks() {
        let xml = """
        <?xml version="1.0"?>
        <rss version="2.0"><channel>
          <title>Feed</title>
          <item><title>First story</title><link>https://example.com/1</link></item>
          <item><title>Second story</title><link>https://example.com/2</link></item>
        </channel></rss>
        """
        let items = RSSFeedParser.parse(Data(xml.utf8))
        XCTAssertEqual(items.count, 2)
        XCTAssertEqual(items[0], RSSItem(title: "First story", link: "https://example.com/1"))
        XCTAssertEqual(items[1].title, "Second story")
    }

    func testDecodesEntitiesAndHandlesCDATA() {
        let xml = """
        <rss><channel>
          <item><title>Bread &amp; Butter</title><link>https://example.com/a</link></item>
          <item><title><![CDATA[Breaking: news]]></title><link>https://example.com/b</link></item>
        </channel></rss>
        """
        let items = RSSFeedParser.parse(Data(xml.utf8))
        XCTAssertEqual(items.count, 2)
        XCTAssertEqual(items[0].title, "Bread & Butter")
        XCTAssertEqual(items[1].title, "Breaking: news")
    }

    func testSkipsItemsWithoutTitle() {
        let xml = """
        <rss><channel>
          <item><link>https://example.com/notitle</link></item>
          <item><title>Has title</title><link>https://example.com/ok</link></item>
        </channel></rss>
        """
        let items = RSSFeedParser.parse(Data(xml.utf8))
        XCTAssertEqual(items.count, 1)
        XCTAssertEqual(items[0].title, "Has title")
    }

    func testEmptyOrGarbageDataYieldsNoItems() {
        XCTAssertTrue(RSSFeedParser.parse(Data()).isEmpty)
        XCTAssertTrue(RSSFeedParser.parse(Data("not xml".utf8)).isEmpty)
    }

    func testExtractsImageFromMediaThumbnail() {
        let xml = """
        <rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
          <item>
            <title>Story</title><link>https://example.com/s</link>
            <media:thumbnail width="240" height="135" url="https://img.example.com/pic.jpg"/>
          </item>
        </channel></rss>
        """
        let items = RSSFeedParser.parse(Data(xml.utf8))
        XCTAssertEqual(items.first?.imageURL, "https://img.example.com/pic.jpg")
    }

    func testExtractsImageFromEnclosure() {
        let xml = """
        <rss><channel>
          <item>
            <title>Story</title><link>https://example.com/s</link>
            <enclosure url="https://img.example.com/photo.png" type="image/png"/>
          </item>
        </channel></rss>
        """
        let items = RSSFeedParser.parse(Data(xml.utf8))
        XCTAssertEqual(items.first?.imageURL, "https://img.example.com/photo.png")
    }

    func testItemWithoutImageHasEmptyImageURL() {
        let xml = "<rss><channel><item><title>No image</title><link>https://x.com</link></item></channel></rss>"
        let items = RSSFeedParser.parse(Data(xml.utf8))
        XCTAssertEqual(items.first?.imageURL, "")
    }

    func testTrimsWhitespaceInTitles() {
        let xml = "<rss><channel><item><title>  Spacey  </title><link> https://x.com </link></item></channel></rss>"
        let items = RSSFeedParser.parse(Data(xml.utf8))
        XCTAssertEqual(items.first?.title, "Spacey")
        XCTAssertEqual(items.first?.link, "https://x.com")
    }
}
