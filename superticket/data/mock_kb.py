"""Mock knowledge base data and search utilities."""

from dataclasses import dataclass


@dataclass
class KBArticle:
    slug: str
    title: str
    category: str
    sub_category: str
    tags: list[str]
    content: str


KB_ARTICLES: list[KBArticle] = [
    KBArticle(
        slug="reset-password",
        title="How to Reset Your Password",
        category="Access",
        sub_category="Account",
        tags=["password", "login", "account"],
        content="1. Visit the password reset page. 2. Enter your email. 3. Click the link in your inbox. 4. Set a new password.",
    ),
    KBArticle(
        slug="unlock-account",
        title="Unlocking a Locked Account",
        category="Access",
        sub_category="Account",
        tags=["account", "lock", "security"],
        content="If your account is locked after too many failed attempts, contact IT or wait 30 minutes for auto-unlock.",
    ),
    KBArticle(
        slug="vpn-setup",
        title="VPN Setup Guide",
        category="Network",
        sub_category="VPN",
        tags=["vpn", "network", "remote"],
        content="Download the VPN client from the portal, install, and connect using your SSO credentials. Contact IT if you experience DNS issues.",
    ),
    KBArticle(
        slug="screen-flicker",
        title="Laptop Screen Flickering",
        category="Hardware",
        sub_category="Laptop",
        tags=["screen", "display", "flicker"],
        content="Update graphics drivers first. If the issue persists, check cable connections or request a hardware replacement.",
    ),
    KBArticle(
        slug="keyboard-sticky",
        title="Sticky Keyboard Keys",
        category="Hardware",
        sub_category="Laptop",
        tags=["keyboard", "keys", "hardware"],
        content="Gently clean under the keycaps with compressed air. Avoid liquids. If keys are physically damaged, open a hardware ticket.",
    ),
    KBArticle(
        slug="app-crash",
        title="Application Keeps Crashing",
        category="Software",
        sub_category="Bug",
        tags=["crash", "app", "software"],
        content="Check for updates, clear cache, and verify system requirements. If reproducible, collect logs and attach to your ticket.",
    ),
    KBArticle(
        slug="printer-setup",
        title="Adding a Network Printer",
        category="Hardware",
        sub_category="Printer",
        tags=["printer", "network", "setup"],
        content="Use the printer IP address or hostname in system settings. Ensure you're on the corporate network (wired or VPN).",
    ),
    KBArticle(
        slug="email-sync",
        title="Email Not Syncing",
        category="Software",
        sub_category="Email",
        tags=["email", "sync", "outlook"],
        content="Verify account settings, check for cached credentials issues, and restart the mail client. Re-add account if necessary.",
    ),
    KBArticle(
        slug="wifi-issues",
        title="Wi-Fi Connectivity Issues",
        category="Network",
        sub_category="Wi-Fi",
        tags=["wifi", "network", "connectivity"],
        content="Forget the network and reconnect. Check if other devices are affected. If only your device, update Wi-Fi drivers.",
    ),
    KBArticle(
        slug="shared-drive",
        title="Accessing Shared Network Drives",
        category="Network",
        sub_category="File Sharing",
        tags=["drive", "share", "files"],
        content="Map the drive using the UNC path. Ensure you have permissions granted by the folder owner or IT.",
    ),
]


def search_kb(query: str | None = None, category: str | None = None, sub_category: str | None = None) -> list[KBArticle]:
    """Search KB articles by query string and/or category filters."""
    results = KB_ARTICLES[:]
    if category:
        results = [a for a in results if a.category.lower() == category.lower()]
    if sub_category:
        results = [a for a in results if a.sub_category.lower() == sub_category.lower()]
    if query:
        q = query.lower()
        results = [
            a for a in results
            if q in a.title.lower() or q in a.content.lower() or any(q in tag.lower() for tag in a.tags)
        ]
    return results


def get_kb_article(slug: str) -> KBArticle | None:
    """Fetch a single KB article by slug."""
    for article in KB_ARTICLES:
        if article.slug == slug:
            return article
    return None
