import Foundation

/// Turns a news headline into a journaling prompt using hand-written,
/// per-language templates — no AI, no network, works on every device. The
/// article supplies the topic; the template supplies the target-language
/// framing (and, being human-written, keeps the grammar correct, which
/// matters in a language-learning app).
///
/// NOTE: the non-English templates should be reviewed by fluent speakers
/// before a real release — they're written to be simple and safe, but a
/// learning app shouldn't ship target-language text unverified.
enum TopicPromptBuilder {
    static let placeholder = "{headline}"

    /// Builds a prompt for a headline. `seed` rotates through the template
    /// pool so consecutive topics don't all use the same framing.
    static func prompt(headline: String, languageCode: String, seed: Int) -> String {
        let pool = newsTemplates[base(languageCode)] ?? newsTemplates["en"]!
        let template = pool[abs(seed) % pool.count]
        return template.replacingOccurrences(of: placeholder, with: headline)
    }

    /// An evergreen prompt for when no article is available (feed down or
    /// news disabled). Not tied to a headline.
    static func evergreen(languageCode: String, seed: Int) -> String {
        let pool = evergreenPrompts[base(languageCode)] ?? evergreenPrompts["en"]!
        return pool[abs(seed) % pool.count]
    }

    private static func base(_ code: String) -> String {
        code.split(whereSeparator: { $0 == "-" || $0 == "_" }).first.map(String.init)?.lowercased()
            ?? code.lowercased()
    }

    static let newsTemplates: [String: [String]] = [
        "en": [
            "In the news today: “{headline}”. What's your reaction? Does it connect to anything in your own life?",
            "Here's a headline: “{headline}”. How does it make you feel, and why?",
            "Someone just read you this: “{headline}”. What would you say back?",
            "Today's story: “{headline}”. Have you experienced anything like this?",
            "“{headline}” — talk through what you think about this.",
        ],
        "es": [
            "Hoy en las noticias: «{headline}». ¿Qué opinas? ¿Te recuerda a algo de tu vida?",
            "Un titular de hoy: «{headline}». ¿Cómo te hace sentir y por qué?",
            "Alguien te lee esto: «{headline}». ¿Qué le responderías?",
            "La historia de hoy: «{headline}». ¿Has vivido algo parecido?",
            "«{headline}» — cuéntame qué piensas sobre esto.",
        ],
        "fr": [
            "À la une aujourd'hui : « {headline} ». Qu'en penses-tu ? Cela te rappelle-t-il quelque chose de ta vie ?",
            "Un titre du jour : « {headline} ». Que ressens-tu, et pourquoi ?",
            "Quelqu'un te lit ceci : « {headline} ». Que répondrais-tu ?",
            "L'histoire du jour : « {headline} ». As-tu déjà vécu quelque chose de semblable ?",
            "« {headline} » — raconte ce que tu en penses.",
        ],
        "zh": [
            "今天的新闻：「{headline}」。你有什么看法？这让你想到自己生活中的什么吗？",
            "今天的一条标题：「{headline}」。你有什么感受，为什么？",
            "有人给你读了这条新闻：「{headline}」。你会怎么回应？",
            "「{headline}」——说说你的想法吧。",
        ],
        "ja": [
            "今日のニュース：「{headline}」。どう思いますか。自分の生活と関係がありますか。",
            "今日の見出し：「{headline}」。どんな気持ちになりますか。なぜですか。",
            "だれかがこれを読んでくれました：「{headline}」。あなたは何と答えますか。",
            "「{headline}」——これについて考えを話してみましょう。",
        ],
        "ar": [
            "في الأخبار اليوم: «{headline}». ما رأيك؟ هل يذكّرك بشيء في حياتك؟",
            "عنوان اليوم: «{headline}». كيف تشعر ولماذا؟",
            "قرأ لك أحدهم هذا: «{headline}». بماذا سترد؟",
            "«{headline}» — تحدّث عمّا تفكر فيه.",
        ],
    ]

    static let evergreenPrompts: [String: [String]] = [
        "en": [
            "Describe a small moment from today worth remembering.",
            "Talk about someone who taught you something important.",
            "Describe a place that makes you feel calm.",
        ],
        "es": [
            "Describe un pequeño momento de hoy que valga la pena recordar.",
            "Habla de alguien que te enseñó algo importante.",
            "Describe un lugar que te haga sentir en calma.",
        ],
        "fr": [
            "Décris un petit moment d'aujourd'hui qui mérite d'être retenu.",
            "Parle de quelqu'un qui t'a appris quelque chose d'important.",
            "Décris un endroit qui t'apaise.",
        ],
        "zh": [
            "描述今天一个值得记住的小瞬间。",
            "说说一个教会你重要事情的人。",
            "描述一个让你感到平静的地方。",
        ],
        "ja": [
            "今日の心に残った小さな瞬間について話してください。",
            "大切なことを教えてくれた人について話してください。",
            "心が落ち着く場所について話してください。",
        ],
        "ar": [
            "صف لحظة صغيرة من اليوم تستحق أن تُتذكَّر.",
            "تحدث عن شخص علّمك شيئًا مهمًا.",
            "صف مكانًا يشعرك بالهدوء.",
        ],
    ]
}
