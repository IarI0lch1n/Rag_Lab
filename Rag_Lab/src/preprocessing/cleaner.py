import html
import re
import unicodedata

from dataclasses import dataclass


@dataclass
class ChunkQualityResult:
    useful: bool
    reason: str | None = None


class TextCleaner:
    MIN_TEXT_CHARS = 120
    MIN_TEXT_WORDS = 15

    VERSION = "2"

    MIN_TEXT_CHARS = 120

    MIN_CODE_CHARS = 80

    WEB_NOISE_PATTERNS = [
        r"^cookie(s)?$",
        r"^accept cookies?$",
        r"^cookie settings$",
        r"^privacy policy$",
        r"^terms( of service| and conditions)?$",
        r"^sign in$",
        r"^log in$",
        r"^login$",
        r"^register$",
        r"^sign up$",
        r"^subscribe$",
        r"^newsletter$",
        r"^advertisement$",
        r"^sponsored$",
        r"^share$",
        r"^share this$",
        r"^read more$",
        r"^load more$",
        r"^back to top$",
        r"^menu$",
        r"^navigation$",
        r"^home$",

        r"^войти$",
        r"^регистрация$",
        r"^зарегистрироваться$",
        r"^подписаться$",
        r"^поделиться$",
        r"^реклама$",
        r"^читать далее$",
        r"^читать ещё$",
        r"^загрузить ещё$",
        r"^наверх$",
        r"^меню$",
        r"^главная$",
        r"^политика конфиденциальности$",
        r"^пользовательское соглашение$",
    ]

    WEB_NOISE_CONTAINS = [
        "we use cookies",
        "this website uses cookies",
        "accept all cookies",
        "manage cookies",

        "используем cookie",
        "используем файлы cookie",
        "согласие на обработку",
        "настройки cookie",

        "all rights reserved",
        "все права защищены",

        "follow us on",
        "подписывайтесь на нас",

        "share on facebook",
        "share on twitter",
        "share on linkedin",
        "поделиться в facebook",
        "поделиться в twitter",
        "поделиться в telegram",
        "поделиться в телеграм",
    ]

    URL_PATTERN = re.compile(
        r"https?://\S+|www\.\S+",
        re.IGNORECASE,
    )

    WORD_PATTERN = re.compile(
        r"[A-Za-zА-Яа-яЁё0-9_]{2,}",
        re.UNICODE,
    )

    def __init__(self) -> None:
        self._compiled_web_noise = [
            re.compile(
                pattern,
                re.IGNORECASE,
            )
            for pattern in self.WEB_NOISE_PATTERNS
        ]

    def clean_document(
        self,
        text: str,
        source_type: str,
        document_type: str | None = None,
    ) -> str:
        if not text:
            return ""

        is_code = self._is_code(
            source_type,
            document_type,
        )

        text = self._normalize_text(
            text
        )

        lines = text.split("\n")

        cleaned_lines = []

        previous_normalized_line = None
        previous_blank = False

        for line in lines:
            cleaned_line = self._clean_line(
                line=line,
                preserve_spacing=is_code,
            )

            if not cleaned_line:
                if (
                    cleaned_lines
                    and not previous_blank
                ):
                    cleaned_lines.append(
                        ""
                    )

                previous_blank = True
                continue

            if (
                source_type == "web"
                and self._is_web_noise_line(
                    cleaned_line
                )
            ):
                continue

            normalized_line = (
                self._normalize_line_for_comparison(
                    cleaned_line
                )
            )

            #
            # Remove immediately repeated lines.
            #
            if (
                normalized_line
                and normalized_line
                == previous_normalized_line
            ):
                continue

            cleaned_lines.append(
                cleaned_line
            )

            previous_normalized_line = (
                normalized_line
            )

            previous_blank = False

        return self._finalize_lines(
            cleaned_lines
        )

    def clean_chunk(
        self,
        text: str,
        source_type: str,
        document_type: str | None = None,
    ) -> str:
        return self.clean_document(
            text=text,
            source_type=source_type,
            document_type=document_type,
        )

    def evaluate_chunk(
        self,
        text: str,
        source_type: str,
        document_type: str | None = None,
    ) -> ChunkQualityResult:
        text = text.strip()

        if not text:
            return ChunkQualityResult(
                useful=False,
                reason="empty",
            )

        if self._is_code(
            source_type,
            document_type,
        ):
            return self._evaluate_code_chunk(
                text
            )

        if (
            len(text)
            < self.MIN_TEXT_CHARS
        ):
            return ChunkQualityResult(
                useful=False,
                reason="too_short",
            )

        words = self.WORD_PATTERN.findall(
            text
        )

        if (
            len(words)
            < self.MIN_TEXT_WORDS
        ):
            return ChunkQualityResult(
                useful=False,
                reason="too_few_words",
            )

        visible_characters = [
            character
            for character in text
            if not character.isspace()
        ]

        if not visible_characters:
            return ChunkQualityResult(
                useful=False,
                reason="no_visible_characters",
            )

        useful_characters = sum(
            1
            for character
            in visible_characters
            if (
                character.isalnum()
                or character
                in ".,:;!?()[]{}+-_=/%'\""
            )
        )

        useful_ratio = (
            useful_characters
            / len(visible_characters)
        )

        if useful_ratio < 0.55:
            return ChunkQualityResult(
                useful=False,
                reason="mostly_symbols",
            )

        url_matches = (
            self.URL_PATTERN.findall(
                text
            )
        )

        #
        # A chunk which is mostly a list of links
        # is usually not useful for semantic RAG.
        #
        if (
            len(url_matches) >= 5
            and len(words) < 40
        ):
            return ChunkQualityResult(
                useful=False,
                reason="mostly_links",
            )

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        if lines:
            noise_lines = sum(
                1
                for line in lines
                if self._is_web_noise_line(
                    line
                )
            )

            if (
                source_type == "web"
                and noise_lines
                / len(lines)
                >= 0.5
            ):
                return ChunkQualityResult(
                    useful=False,
                    reason="web_boilerplate",
                )

        return ChunkQualityResult(
            useful=True
        )

    def _evaluate_code_chunk(
        self,
        text: str,
    ) -> ChunkQualityResult:
        if (
            len(text)
            < self.MIN_CODE_CHARS
        ):
            return ChunkQualityResult(
                useful=False,
                reason="code_too_short",
            )

        identifiers = re.findall(
            r"[A-Za-z_][A-Za-z0-9_]{2,}",
            text,
        )

        if len(identifiers) < 3:
            return ChunkQualityResult(
                useful=False,
                reason="not_enough_code_content",
            )

        return ChunkQualityResult(
            useful=True
        )

    def _is_web_noise_line(
        self,
        line: str,
    ) -> bool:
        normalized = (
            line.strip()
            .casefold()
        )

        if not normalized:
            return True

        for pattern in (
            self._compiled_web_noise
        ):
            if pattern.match(
                normalized
            ):
                return True

        for phrase in (
            self.WEB_NOISE_CONTAINS
        ):
            if phrase in normalized:
                return True

        #
        # Social-only navigation line.
        #
        social_words = {
            "facebook",
            "twitter",
            "x",
            "linkedin",
            "telegram",
            "youtube",
            "instagram",
            "vk",
        }

        tokens = {
            token.casefold()
            for token
            in self.WORD_PATTERN.findall(
                normalized
            )
        }

        if (
            tokens
            and tokens.issubset(
                social_words
            )
        ):
            return True

        return False

    @staticmethod
    def _is_code(
        source_type: str,
        document_type: str | None,
    ) -> bool:
        return (
            source_type == "git"
            and document_type == "code"
        )

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        text = html.unescape(
            text
        )

        text = unicodedata.normalize(
            "NFKC",
            text,
        )

        text = (
            text
            .replace(
                "\u200b",
                "",
            )
            .replace(
                "\u200c",
                "",
            )
            .replace(
                "\u200d",
                "",
            )
            .replace(
                "\ufeff",
                "",
            )
            .replace(
                "\xa0",
                " ",
            )
            .replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
        )

        return text

    @staticmethod
    def _clean_line(
        line: str,
        preserve_spacing: bool,
    ) -> str:
        line = line.rstrip()

        if preserve_spacing:
            return line

        return re.sub(
            r"[ \t]+",
            " ",
            line,
        ).strip()

    @staticmethod
    def _normalize_line_for_comparison(
        line: str,
    ) -> str:
        return re.sub(
            r"\s+",
            " ",
            line,
        ).strip().casefold()

    @staticmethod
    def _finalize_lines(
        lines: list[str],
    ) -> str:
        while (
            lines
            and not lines[0]
        ):
            lines.pop(0)

        while (
            lines
            and not lines[-1]
        ):
            lines.pop()

        result = []

        previous_blank = False

        for line in lines:
            is_blank = not line

            if (
                is_blank
                and previous_blank
            ):
                continue

            result.append(
                line
            )

            previous_blank = is_blank

        return "\n".join(
            result
        ).strip()


text_cleaner = TextCleaner()