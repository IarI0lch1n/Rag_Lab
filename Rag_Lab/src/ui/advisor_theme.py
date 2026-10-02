from nicegui import ui


def apply_advisor_theme() -> None:

    ui.colors(
        primary="#9CC7D8",
        secondary="#B8904F",
        accent="#D2B16B",
        dark="#11171B",
        positive="#799A7A",
        negative="#A85B52",
        warning="#C39552",
        info="#7797A6",
    )

    ui.add_css(
        """
        :root {
            --advisor-bg: #0f1519;
            --advisor-bg-soft: #151d22;
            --advisor-panel: #182126;
            --advisor-panel-2: #1c272d;

            --advisor-border: #34444c;
            --advisor-border-soft: #29373e;

            --advisor-text: #d9e1e3;
            --advisor-muted: #82949c;

            --advisor-ice: #9cc7d8;
            --advisor-ice-bright: #c3e5ef;

            --advisor-brass: #b8904f;
            --advisor-brass-bright: #d2b16b;

            --advisor-danger: #a85b52;
        }

        html,
        body,
        #app {
            background:
                radial-gradient(
                    circle at 75% 0%,
                    rgba(116, 155, 170, 0.10),
                    transparent 32%
                ),
                linear-gradient(
                    180deg,
                    #131b20 0%,
                    #0d1215 100%
                ) !important;

            color: var(--advisor-text);
        }

        body {
            font-family:
                "Segoe UI",
                Arial,
                sans-serif;
        }

        ::selection {
            background: rgba(156, 199, 216, 0.30);
        }

        .rag-header {
            background:
                linear-gradient(
                    180deg,
                    #1b252b 0%,
                    #12191d 100%
                ) !important;

            color: var(--advisor-text) !important;

            border-bottom:
                1px solid
                var(--advisor-brass);

            box-shadow:
                0 4px 18px
                rgba(0, 0, 0, 0.35);
        }

        .source-panel {
            background:
                linear-gradient(
                    180deg,
                    #172026 0%,
                    #11181c 100%
                ) !important;

            border-right:
                1px solid
                var(--advisor-border);
        }

        .chat-panel {
            background:
                linear-gradient(
                    180deg,
                    #11181c 0%,
                    #0d1316 100%
                ) !important;
        }

        .source-card {
            background:
                linear-gradient(
                    145deg,
                    #1d282e,
                    #172026
                ) !important;

            color:
                var(--advisor-text) !important;

            border:
                1px solid
                var(--advisor-border) !important;

            border-radius:
                3px !important;

            box-shadow:
                inset 0 1px 0
                rgba(255, 255, 255, 0.025);
        }

        .source-card:hover {
            border-color:
                var(--advisor-ice) !important;

            box-shadow:
                0 0 0 1px
                rgba(156, 199, 216, 0.08),
                0 8px 24px
                rgba(0, 0, 0, 0.30);
        }

        .source-uri {
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .advisor-title {
            color:
                var(--advisor-ice-bright) !important;

            letter-spacing: 0.16em;
            font-weight: 700;
        }

        .advisor-subtitle {
            color:
                var(--advisor-brass-bright) !important;

            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .advisor-logo {
            color:
                var(--advisor-ice-bright) !important;

            filter:
                drop-shadow(
                    0 0 7px
                    rgba(156, 199, 216, 0.35)
                );
        }

        .advisor-section-title {
            color:
                var(--advisor-text) !important;

            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .advisor-muted {
            color:
                var(--advisor-muted) !important;
        }

        .q-separator {
            background:
                var(--advisor-border-soft) !important;
        }

        .q-card {
            background:
                var(--advisor-panel) !important;

            color:
                var(--advisor-text) !important;
        }

        .q-field__control {
            background:
                rgba(10, 15, 18, 0.58) !important;

            color:
                var(--advisor-text) !important;
        }

        .q-field__native,
        .q-field__input,
        .q-field__label {
            color:
                var(--advisor-text) !important;
        }

        .q-field__bottom,
        .text-grey-5,
        .text-grey-6,
        .text-grey-7 {
            color:
                var(--advisor-muted) !important;
        }

        .q-btn {
            letter-spacing: 0.04em;
        }

        .q-btn.bg-primary {
            background:
                #456979 !important;

            color:
                #eef8fb !important;
        }

        a {
            color:
                var(--advisor-ice) !important;
        }

        .q-menu {
            background:
                var(--advisor-panel-2) !important;

            color:
                var(--advisor-text) !important;

            border:
                1px solid
                var(--advisor-border);
        }

        .q-item:hover {
            background:
                rgba(156, 199, 216, 0.08) !important;
        }

        .q-badge {
            border-radius: 2px !important;
        }

        * {
            scrollbar-color:
                #536b76
                #10171b;
        }

        ::-webkit-scrollbar {
            width: 9px;
            height: 9px;
        }

        ::-webkit-scrollbar-track {
            background: #10171b;
        }

        ::-webkit-scrollbar-thumb {
            background: #536b76;
            border: 2px solid #10171b;
        }
        """
    )