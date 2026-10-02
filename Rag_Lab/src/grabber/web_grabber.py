import logging

from collections import deque
from pathlib import Path
from urllib.parse import (
    parse_qsl,
    quote,
    urlencode,
    unquote,
    urljoin,
    urlsplit,
    urlunsplit,
)

import httpx

from bs4 import BeautifulSoup

from src.config import settings

from src.db.models import Source

from src.grabber.base import (
    BaseGrabber,
    GrabbedDocument,
)


logger = logging.getLogger(
    __name__
)


class WebGrabber(BaseGrabber):

    TIMEOUT = 20.0

    USER_AGENT = (
        "Advisor-RAG/1.0 "
        "(educational knowledge indexer)"
    )

    IGNORED_QUERY_PARAMETERS = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
    }

    ALLOWED_EXTENSIONS = {
        "",
        ".html",
        ".htm",
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".xml",
        ".csv",
        ".pdf",
        ".docx",
        ".pptx",
    }

    SKIPPED_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".mp3",
        ".wav",
        ".ogg",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".zip",
        ".rar",
        ".7z",
        ".exe",
        ".msi",
        ".css",
        ".js",
        ".map",
    }

    IGNORED_PATH_PARTS = {
        "login",
        "logout",
        "signin",
        "signup",
        "register",
        "search",
        "account",
        "profile",
        "settings",
        "privacy",
        "terms",
        "feed",
        "feedback",
        "sandbox",
    }

    FANDOM_IGNORED_PREFIXES = {
        "File:",
        "Category:",
        "Template:",
        "User:",
        "User_talk:",
        "Talk:",
        "Special:",
        "Forum:",
        "Message_Wall:",
        "MediaWiki:",
        "Help:",
        "Thread:",
        "Blog:",
    }

    def grab(
        self,
        source: Source,
    ) -> list[GrabbedDocument]:

        if source.source_type != "web":
            raise ValueError(
                f"WebGrabber cannot process "
                f"source type "
                f"'{source.source_type}'."
            )

        if not source.uri:
            raise ValueError(
                f"Source {source.id} "
                f"has no URL."
            )

        root_url = (
            self.normalize_url(
                source.uri
            )
        )

        #
        # Fandom / MediaWiki needs API-based
        # retrieval because direct HTML may
        # return HTTP 403.
        #
        if self._is_fandom_url(
            root_url
        ):
            return (
                self._grab_fandom(
                    root_url
                )
            )

        return (
            self._grab_standard_site(
                root_url
            )
        )

    def _grab_standard_site(
        self,
        root_url: str,
    ) -> list[GrabbedDocument]:

        root_host = (
            urlsplit(
                root_url
            ).hostname
            or ""
        ).lower()

        max_pages = (
            settings
            .web_crawl_max_pages
        )

        max_depth = (
            settings
            .web_crawl_max_depth
        )

        queue = deque(
            [
                (
                    root_url,
                    0,
                    None,
                )
            ]
        )

        visited = set()

        documents = []

        print()
        print(
            f"[Web] Crawling: "
            f"{root_url}"
        )

        print(
            f"[Web] Max pages: "
            f"{max_pages}"
        )

        print(
            f"[Web] Max depth: "
            f"{max_depth}"
        )

        with httpx.Client(
            follow_redirects=True,
            timeout=self.TIMEOUT,
            headers={
                "User-Agent": (
                    self.USER_AGENT
                ),
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "application/pdf,"
                    "text/plain,"
                    "*/*;q=0.8"
                ),
            },
        ) as client:

            while (
                queue
                and len(documents)
                < max_pages
            ):

                (
                    url,
                    depth,
                    parent_url,
                ) = queue.popleft()

                try:

                    normalized_url = (
                        self.normalize_url(
                            url
                        )
                    )

                except ValueError:
                    continue

                if (
                    normalized_url
                    in visited
                ):
                    continue

                visited.add(
                    normalized_url
                )

                try:

                    response = (
                        client.get(
                            normalized_url
                        )
                    )

                    response.raise_for_status()

                except Exception as exc:

                    logger.warning(
                        "Could not fetch %s: %s",
                        normalized_url,
                        exc,
                    )

                    if (
                        normalized_url
                        == root_url
                        and not documents
                    ):
                        raise RuntimeError(
                            f"Could not download "
                            f"'{root_url}': "
                            f"{exc}"
                        ) from exc

                    continue

                final_url = (
                    self.normalize_url(
                        str(
                            response.url
                        )
                    )
                )

                visited.add(
                    final_url
                )

                content_type = (
                    response
                    .headers
                    .get(
                        "content-type",
                        "",
                    )
                    .split(";")[0]
                    .strip()
                    .lower()
                )

                extension = (
                    Path(
                        urlsplit(
                            final_url
                        ).path
                    )
                    .suffix
                    .lower()
                )

                if self._is_html(
                    content_type,
                    extension,
                ):

                    document = (
                        self
                        ._create_html_document(
                            response=response,
                            url=final_url,
                            root_url=root_url,
                            depth=depth,
                            parent_url=(
                                parent_url
                            ),
                        )
                    )

                    documents.append(
                        document
                    )

                    print(
                        f"[Web] "
                        f"{len(documents)}/"
                        f"{max_pages} "
                        f"depth={depth} "
                        f"{final_url}"
                    )

                    if depth < max_depth:

                        links = (
                            self._extract_links(
                                html=(
                                    response.content
                                ),
                                base_url=(
                                    final_url
                                ),
                                root_host=(
                                    root_host
                                ),
                            )
                        )

                        for link in links:

                            if (
                                link
                                not in visited
                            ):

                                queue.append(
                                    (
                                        link,
                                        depth + 1,
                                        final_url,
                                    )
                                )

                elif (
                    self
                    ._is_supported_document(
                        extension,
                        content_type,
                    )
                ):

                    documents.append(
                        GrabbedDocument(
                            name=(
                                self._get_filename(
                                    final_url
                                )
                            ),
                            content=(
                                response.content
                            ),
                            mime_type=(
                                content_type
                                or None
                            ),
                            file_extension=(
                                extension
                                or None
                            ),
                            external_id=(
                                final_url
                            ),
                            metadata={
                                "source": "web",
                                "crawl_mode": (
                                    "website"
                                ),
                                "url": (
                                    final_url
                                ),
                                "parent_url": (
                                    parent_url
                                ),
                                "crawl_depth": (
                                    depth
                                ),
                                "is_root": (
                                    final_url
                                    == root_url
                                ),
                            },
                        )
                    )

        if not documents:

            raise ValueError(
                f"No supported documents "
                f"were found at "
                f"'{root_url}'."
            )

        print(
            f"[Web] Crawl completed: "
            f"{len(documents)} documents."
        )

        return documents

    def _grab_fandom(
        self,
        root_url: str,
    ) -> list[GrabbedDocument]:

        parsed_root = (
            urlsplit(
                root_url
            )
        )

        host = (
            parsed_root.hostname
            or ""
        ).lower()

        path = (
            parsed_root.path
        )

        if "/wiki/" not in path:

            raise ValueError(
                "Fandom source must point "
                "to a wiki article URL."
            )

        root_title = (
            unquote(
                path.split(
                    "/wiki/",
                    1,
                )[1]
            )
        )

        if not root_title:

            raise ValueError(
                "Could not determine "
                "the Fandom article title."
            )

        api_url = (
            f"{parsed_root.scheme}"
            f"://{host}/api.php"
        )

        max_pages = (
            settings
            .web_crawl_max_pages
        )

        max_depth = (
            settings
            .web_crawl_max_depth
        )

        queue = deque(
            [
                (
                    root_title,
                    0,
                    None,
                )
            ]
        )

        visited = set()

        documents = []

        print()
        print(
            f"[Fandom] Wiki: "
            f"{host}"
        )

        print(
            f"[Fandom] Root article: "
            f"{root_title}"
        )

        print(
            f"[Fandom] Max pages: "
            f"{max_pages}"
        )

        print(
            f"[Fandom] Max depth: "
            f"{max_depth}"
        )

        with httpx.Client(
            follow_redirects=True,
            timeout=self.TIMEOUT,
            headers={
                "User-Agent": (
                    self.USER_AGENT
                ),
                "Accept": (
                    "application/json,"
                    "text/plain;q=0.8"
                ),
            },
        ) as client:

            while (
                queue
                and len(documents)
                < max_pages
            ):

                (
                    page_title,
                    depth,
                    parent_url,
                ) = queue.popleft()

                normalized_title = (
                    page_title
                    .replace("_", " ")
                    .strip()
                )

                key = (
                    normalized_title
                    .casefold()
                )

                if key in visited:
                    continue

                visited.add(
                    key
                )

                try:

                    response = (
                        client.get(
                            api_url,
                            params={
                                "action": (
                                    "parse"
                                ),
                                "page": (
                                    normalized_title
                                ),
                                "prop": (
                                    "text"
                                ),
                                "redirects": (
                                    "1"
                                ),
                                "format": (
                                    "json"
                                ),
                            },
                        )
                    )

                    response.raise_for_status()

                    data = (
                        response.json()
                    )

                except Exception as exc:

                    logger.warning(
                        (
                            "Could not fetch "
                            "Fandom article "
                            "%s: %s"
                        ),
                        normalized_title,
                        exc,
                    )

                    if (
                        not documents
                        and key
                        == (
                            root_title
                            .replace(
                                "_",
                                " "
                            )
                            .casefold()
                        )
                    ):

                        raise RuntimeError(
                            "Could not retrieve "
                            "the Fandom article "
                            "through MediaWiki API: "
                            f"{exc}"
                        ) from exc

                    continue

                if "error" in data:

                    logger.warning(
                        (
                            "Fandom API error "
                            "for %s: %s"
                        ),
                        normalized_title,
                        data["error"],
                    )

                    continue

                parse_data = (
                    data.get(
                        "parse"
                    )
                    or {}
                )

                resolved_title = (
                    parse_data.get(
                        "title"
                    )
                    or normalized_title
                )

                raw_html = (
                    parse_data.get(
                        "text"
                    )
                )

                if isinstance(
                    raw_html,
                    dict,
                ):

                    raw_html = (
                        raw_html.get(
                            "*"
                        )
                        or ""
                    )

                if not raw_html:

                    continue

                article_path = quote(
                    resolved_title
                    .replace(
                        " ",
                        "_"
                    ),
                    safe="/:'()-",
                )

                article_url = (
                    f"{parsed_root.scheme}"
                    f"://{host}"
                    f"/wiki/"
                    f"{article_path}"
                )

                complete_html = (
                    "<html>"
                    "<head>"
                    "<meta charset='utf-8'>"
                    f"<title>"
                    f"{resolved_title}"
                    f"</title>"
                    "</head>"
                    "<body>"
                    f"{raw_html}"
                    "</body>"
                    "</html>"
                )

                html_bytes = (
                    complete_html.encode(
                        "utf-8"
                    )
                )

                documents.append(
                    GrabbedDocument(
                        name=(
                            resolved_title
                        ),
                        content=(
                            html_bytes
                        ),
                        mime_type=(
                            "text/html"
                        ),
                        file_extension=(
                            ".html"
                        ),
                        external_id=(
                            article_url
                        ),
                        metadata={
                            "source": "web",
                            "platform": (
                                "fandom"
                            ),
                            "crawl_mode": (
                                "website"
                            ),
                            "url": (
                                article_url
                            ),
                            "parent_url": (
                                parent_url
                            ),
                            "crawl_depth": (
                                depth
                            ),
                            "is_root": (
                                len(documents)
                                == 1
                            ),
                        },
                    )
                )

                print(
                    f"[Fandom] "
                    f"{len(documents)}/"
                    f"{max_pages} "
                    f"depth={depth} "
                    f"{resolved_title}"
                )

                if depth >= max_depth:
                    continue

                links = (
                    self
                    ._extract_fandom_links(
                        html=(
                            html_bytes
                        ),
                        base_url=(
                            article_url
                        ),
                        host=(
                            host
                        ),
                    )
                )

                for (
                    linked_title,
                    linked_url,
                ) in links:

                    linked_key = (
                        linked_title
                        .replace(
                            "_",
                            " "
                        )
                        .casefold()
                    )

                    if (
                        linked_key
                        in visited
                    ):
                        continue

                    queue.append(
                        (
                            linked_title,
                            depth + 1,
                            article_url,
                        )
                    )

        if not documents:

            raise ValueError(
                "No Fandom wiki articles "
                "could be retrieved."
            )

        print(
            f"[Fandom] Crawl completed: "
            f"{len(documents)} articles."
        )

        return documents

    def _extract_fandom_links(
        self,
        html: bytes,
        base_url: str,
        host: str,
    ) -> list[
        tuple[str, str]
    ]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        found = {}

        for anchor in soup.find_all(
            "a",
            href=True,
        ):

            href = (
                anchor.get(
                    "href"
                )
                or ""
            ).strip()

            if not href:
                continue

            absolute_url = (
                urljoin(
                    base_url,
                    href,
                )
            )

            parsed = (
                urlsplit(
                    absolute_url
                )
            )

            if (
                (
                    parsed.hostname
                    or ""
                ).lower()
                != host
            ):
                continue

            if not (
                parsed.path
                .startswith(
                    "/wiki/"
                )
            ):
                continue

            raw_title = (
                unquote(
                    parsed.path[
                        len(
                            "/wiki/"
                        ):
                    ]
                )
            )

            if not raw_title:
                continue

            title = (
                raw_title
                .replace(
                    "_",
                    " "
                )
                .strip()
            )

            if (
                self
                ._is_ignored_fandom_title(
                    title
                )
            ):
                continue

            normalized_url = (
                f"{parsed.scheme}"
                f"://{host}"
                f"{parsed.path}"
            )

            found[
                title.casefold()
            ] = (
                title,
                normalized_url,
            )

        return list(
            found.values()
        )

    def _is_ignored_fandom_title(
        self,
        title: str,
    ) -> bool:

        lowered = (
            title.casefold()
        )

        for prefix in (
            self
            .FANDOM_IGNORED_PREFIXES
        ):

            if lowered.startswith(
                prefix.casefold()
            ):
                return True

        return False

    @staticmethod
    def _is_fandom_url(
        url: str,
    ) -> bool:

        hostname = (
            urlsplit(
                url
            ).hostname
            or ""
        ).lower()

        return (
            hostname.endswith(
                ".fandom.com"
            )
        )

    def _create_html_document(
        self,
        response: httpx.Response,
        url: str,
        root_url: str,
        depth: int,
        parent_url: str | None,
    ) -> GrabbedDocument:

        soup = BeautifulSoup(
            response.content,
            "html.parser",
        )

        title = None

        if soup.title:

            title = (
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

        if not title:

            title = (
                self._get_filename(
                    url
                )
            )

        return GrabbedDocument(
            name=title,
            content=(
                response.content
            ),
            mime_type="text/html",
            file_extension=".html",
            external_id=url,
            metadata={
                "source": "web",
                "crawl_mode": (
                    "website"
                ),
                "url": url,
                "parent_url": (
                    parent_url
                ),
                "crawl_depth": (
                    depth
                ),
                "is_root": (
                    url == root_url
                ),
            },
        )

    def _extract_links(
        self,
        html: bytes,
        base_url: str,
        root_host: str,
    ) -> list[str]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        content_root = (
            soup.find(
                "main"
            )
            or soup.find(
                "article"
            )
            or soup.find(
                attrs={
                    "role": "main"
                }
            )
            or soup.body
            or soup
        )

        links = set()

        for anchor in (
            content_root.find_all(
                "a",
                href=True,
            )
        ):

            href = (
                anchor.get(
                    "href"
                )
                or ""
            ).strip()

            if not href:
                continue

            if href.startswith(
                (
                    "#",
                    "mailto:",
                    "tel:",
                    "javascript:",
                    "data:",
                )
            ):
                continue

            absolute_url = (
                urljoin(
                    base_url,
                    href,
                )
            )

            try:

                normalized_url = (
                    self.normalize_url(
                        absolute_url
                    )
                )

            except ValueError:
                continue

            parsed = (
                urlsplit(
                    normalized_url
                )
            )

            hostname = (
                parsed.hostname
                or ""
            ).lower()

            if (
                hostname
                != root_host
            ):
                continue

            if (
                self._is_ignored_path(
                    parsed.path
                )
            ):
                continue

            extension = (
                Path(
                    parsed.path
                )
                .suffix
                .lower()
            )

            if (
                extension
                in self
                .SKIPPED_EXTENSIONS
            ):
                continue

            if (
                extension
                and extension
                not in self
                .ALLOWED_EXTENSIONS
            ):
                continue

            links.add(
                normalized_url
            )

        return sorted(
            links
        )

    def _is_ignored_path(
        self,
        path: str,
    ) -> bool:

        parts = {
            part.casefold()
            for part
            in path.split("/")
            if part
        }

        return bool(
            parts
            & self.IGNORED_PATH_PARTS
        )

    @staticmethod
    def _is_html(
        content_type: str,
        extension: str,
    ) -> bool:

        if content_type in {
            "text/html",
            "application/xhtml+xml",
        }:
            return True

        if (
            content_type
            and content_type
            not in {
                "application/octet-stream",
            }
        ):
            return False

        return extension in {
            "",
            ".html",
            ".htm",
        }

    def _is_supported_document(
        self,
        extension: str,
        content_type: str,
    ) -> bool:

        if (
            extension
            in self.ALLOWED_EXTENSIONS
        ):
            return True

        return content_type in {
            "application/pdf",
            "text/plain",
            "text/markdown",
            "text/csv",
            "application/json",
            "application/xml",
            "text/xml",
            (
                "application/vnd."
                "openxmlformats-"
                "officedocument."
                "wordprocessingml."
                "document"
            ),
            (
                "application/vnd."
                "openxmlformats-"
                "officedocument."
                "presentationml."
                "presentation"
            ),
        }

    def normalize_url(
        self,
        url: str,
    ) -> str:

        parsed = (
            urlsplit(
                url.strip()
            )
        )

        if (
            parsed.scheme.lower()
            not in {
                "http",
                "https",
            }
        ):
            raise ValueError(
                f"Unsupported URL: "
                f"{url}"
            )

        host = (
            parsed.hostname
            or ""
        ).lower()

        if not host:

            raise ValueError(
                f"Invalid URL: "
                f"{url}"
            )

        scheme = (
            parsed.scheme.lower()
        )

        port = (
            parsed.port
        )

        if (
            port
            and not (
                scheme == "http"
                and port == 80
            )
            and not (
                scheme == "https"
                and port == 443
            )
        ):

            netloc = (
                f"{host}:{port}"
            )

        else:

            netloc = host

        query_items = [
            (
                key,
                value,
            )
            for key, value
            in parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
            if (
                key.lower()
                not in self
                .IGNORED_QUERY_PARAMETERS
            )
        ]

        query_items.sort()

        query = (
            urlencode(
                query_items,
                doseq=True,
            )
        )

        path = (
            parsed.path
            or "/"
        )

        if path != "/":

            path = (
                path.rstrip("/")
            )

        return urlunsplit(
            (
                scheme,
                netloc,
                path,
                query,
                "",
            )
        )

    @staticmethod
    def _get_filename(
        url: str,
    ) -> str:

        parsed = (
            urlsplit(
                url
            )
        )

        filename = (
            unquote(
                Path(
                    parsed.path
                ).name
            )
        )

        if filename:
            return filename

        return (
            parsed.hostname
            or "web-document"
        )


web_grabber = WebGrabber()