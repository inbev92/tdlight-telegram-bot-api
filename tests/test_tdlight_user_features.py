#!/usr/bin/env python3
"""Executable contract tests for TDLight user-only extensions.

These source-level tests are intentionally lightweight: the upstream project has no
unit-test target for telegram-bot-api, while the production C++ build remains the
final integration check.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLIENT_CPP = (ROOT / "telegram-bot-api/Client.cpp").read_text()
CLIENT_H = (ROOT / "telegram-bot-api/Client.h").read_text()
PARAMETERS_H = (ROOT / "telegram-bot-api/ClientParameters.h").read_text()
MAIN_CPP = (ROOT / "telegram-bot-api/telegram-bot-api.cpp").read_text()
ENTRYPOINT = (ROOT / "docker-entrypoint.sh").read_text()
README = (ROOT / "README.md").read_text()
OPENAPI = (ROOT / "tdlight-api-openapi.yaml").read_text()


class GetChatHistoryContractTest(unittest.TestCase):
    def test_user_only_method_is_registered_and_declared(self):
        self.assertIn('methods_.emplace("getchathistory", &Client::process_get_chat_history_query);', CLIENT_CPP)
        self.assertIn("td::Status process_get_chat_history_query(PromisedQueryPtr &query);", CLIENT_H)

    def test_handler_validates_tdlib_bounds_and_dispatches_get_chat_history(self):
        match = re.search(
            r"td::Status Client::process_get_chat_history_query\(PromisedQueryPtr &query\) \{(?P<body>.*?)\n\}",
            CLIENT_CPP,
            re.S,
        )
        self.assertIsNotNone(match)
        assert match is not None
        body = match.group("body")
        self.assertIn("CHECK_IS_USER();", body)
        self.assertRegex(body, r'get_message_id\(query\.get\(\), "from_message_id"\)')
        self.assertRegex(body, r'get_integer_arg\(query\.get\(\), "offset", 0, -99, 0\)')
        self.assertRegex(body, r'get_integer_arg\(query\.get\(\), "limit", 100, 1, 100\)')
        self.assertIn("limit < -offset", body)
        self.assertIn('to_bool(query->arg("only_local"))', body)
        self.assertIn("make_object<td_api::getChatHistory>", body)
        self.assertIn("TdOnGetMessagesCallback", body)

    def test_readme_and_openapi_document_user_only_method(self):
        self.assertIn("getChatHistory", README)
        self.assertIn("/getChatHistory:", OPENAPI)
        history_path = OPENAPI.split("/getChatHistory:", 1)[1].split("\n  /", 1)[0]
        self.assertIn("user-only", history_path)
        self.assertIn("#/components/schemas/GetChatHistoryRequest", history_path)
        request_schema = OPENAPI.split("    GetChatHistoryRequest:", 1)[1].split("\n    Error:", 1)[0]
        for parameter in ("chat_id", "from_message_id", "offset", "limit", "only_local"):
            self.assertIn(f"{parameter}:", request_schema)


class OutgoingUpdatesContractTest(unittest.TestCase):
    def test_option_defaults_off_and_only_bypasses_outgoing_skip_for_users(self):
        self.assertIn("bool user_updates_include_outgoing_ = false;", PARAMETERS_H)
        self.assertIn('"user-updates-include-outgoing"', MAIN_CPP)
        self.assertRegex(
            CLIENT_CPP,
            r"message_info->is_outgoing\s*&&\s*chat_id != 0\s*&&\s*!\(is_user_\s*&&\s*parameters_->user_updates_include_outgoing_\)",
        )

    def test_user_message_json_exposes_direction(self):
        self.assertRegex(
            CLIENT_CPP,
            r'if \(client_->is_user_\) \{\s*object\("is_outgoing", td::JsonBool\(message_->is_outgoing\)\);\s*\}',
        )
        self.assertIn("is_outgoing:", OPENAPI)

    def test_docker_environment_and_documentation_are_wired(self):
        self.assertIn("TELEGRAM_USER_UPDATES_INCLUDE_OUTGOING", ENTRYPOINT)
        self.assertIn("--user-updates-include-outgoing", ENTRYPOINT)
        self.assertRegex(
            ENTRYPOINT,
            r'case "\$\{TELEGRAM_USER_UPDATES_INCLUDE_OUTGOING:-\}" in\s*1\|true\|TRUE\|yes\|YES\)',
        )
        self.assertIn("--user-updates-include-outgoing", README)
        self.assertIn("TELEGRAM_USER_UPDATES_INCLUDE_OUTGOING", README)


if __name__ == "__main__":
    unittest.main()
