import re

CATEGORY_KEYWORDS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        "billing",
        frozenset(
            {
                "refund",
                "charge",
                "charged",
                "invoice",
                "payment",
                "billing",
                "subscription",
                "price",
            }
        ),
    ),
    (
        "technical",
        frozenset(
            {"error", "crash", "crashes", "bug", "broken", "slow", "freezes", "fails"}
        ),
    ),
    (
        "account",
        frozenset({"password", "login", "account", "username", "locked", "access"}),
    ),
)

HIGH_URGENCY_KEYWORDS = frozenset(
    {"urgent", "immediately", "asap", "emergency", "critical", "outage"}
)
MEDIUM_URGENCY_KEYWORDS = frozenset(
    {"issue", "problem", "waiting", "delay", "delayed"}
)

NEGATIVE_KEYWORDS = frozenset(
    {
        "angry",
        "terrible",
        "awful",
        "worst",
        "unacceptable",
        "frustrated",
        "disappointed",
        "furious",
        "ridiculous",
    }
)
POSITIVE_KEYWORDS = frozenset(
    {"thanks", "thank", "great", "love", "appreciate", "awesome", "excellent", "happy"}
)

DRAFT_REPLIES: dict[str, str] = {
    "billing": (
        "Thank you for contacting us about your billing question. "
        "We are reviewing the charges on your account and will follow up "
        "with the details shortly."
    ),
    "technical": (
        "Thank you for reporting this problem. "
        "Our technical team is looking into it. "
        "We will update you as soon as we know more."
    ),
    "account": (
        "Thank you for contacting us about your account. "
        "We will help you restore access and confirm once it is done."
    ),
    "other": (
        "Thank you for getting in touch. "
        "We have received your message and will reply shortly."
    ),
}


def _words(message: str) -> set[str]:
    return set(re.findall(r"[a-z']+", message.lower()))


def classify_category(message: str) -> str:
    words = _words(message)
    for category, keywords in CATEGORY_KEYWORDS:
        if words & keywords:
            return category
    return "other"


def classify_urgency(message: str) -> str:
    words = _words(message)
    if words & HIGH_URGENCY_KEYWORDS:
        return "high"
    if words & MEDIUM_URGENCY_KEYWORDS:
        return "medium"
    return "low"


def classify_sentiment(message: str) -> str:
    words = _words(message)
    if words & NEGATIVE_KEYWORDS:
        return "negative"
    if words & POSITIVE_KEYWORDS:
        return "positive"
    return "neutral"


def draft_reply(category: str) -> str:
    return DRAFT_REPLIES[category]
