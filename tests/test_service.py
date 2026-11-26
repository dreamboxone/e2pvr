# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from E2PVR.service import read_key, read_keys, ServiceError
from E2PVR.live import open_live, probe_live, connection_error
import socket


class ServiceTests(unittest.TestCase):
    def test_live_probe_requires_setup_and_closes_session(self):
        session = MagicMock()
        session.ready.is_set.return_value = False
        session.error = "API key rejected"
        with patch("E2PVR.live.read_keys", return_value=["test-key"]), \
                patch("E2PVR.live.LiveSession", return_value=session), patch("E2PVR.live.logger"):
            with self.assertRaisesRegex(ServiceError, "API key rejected"):
                probe_live("ru")
        session.close.assert_called_once()

    def test_quota_failure_tries_next_key_without_old_resume_handle(self):
        blocked, working = MagicMock(), MagicMock()
        blocked.ready.is_set.return_value = False
        blocked.error = "Service quota exceeded"
        working.ready.is_set.return_value = True
        working.closed.is_set.return_value = False
        callback = MagicMock()
        with patch("E2PVR.live.read_keys", return_value=["first", "second"]), \
                patch("E2PVR.live.LiveSession", side_effect=[blocked, working]) as connect, patch("E2PVR.live.logger"):
            self.assertIs(open_live("fa", callback, "first", "old-handle"), working)
        self.assertEqual([call.args[2:] for call in connect.call_args_list],
                         [("first", "old-handle"), ("second", None)])
        blocked.close.assert_called_once()
        working.close.assert_not_called()

    def test_network_failure_does_not_rotate_keys(self):
        with patch("E2PVR.live.read_keys", return_value=["first", "second"]), \
                patch("E2PVR.live.LiveSession", side_effect=socket.gaierror(-3, "failure")) as connect:
            with self.assertRaisesRegex(ServiceError, "DNS"):
                open_live("fa", MagicMock())
        connect.assert_called_once()

    def test_key_file_preserves_priority_and_skips_blank_invalid_and_duplicate_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "key")
            with open(path, "w", encoding="utf-8-sig") as stream:
                stream.write("  first\n\nsecond\nfirst\nbad key\n third  \n")
            self.assertEqual(read_keys(path), ["first", "second", "third"])

    def test_dns_failure_is_distinct_from_key_rejection(self):
        self.assertIn("DNS", connection_error(socket.gaierror(-3, "failure")))

    def test_dotted_key_and_bom_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory,"key")
            with open(path,"w",encoding="utf-8-sig") as stream:
                stream.write("  Example.token_with-dots.123456789\n")
            self.assertEqual(read_key(path), "Example.token_with-dots.123456789")

    def test_empty_or_missing_file_does_not_look_like_authentication_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "key")
            with self.assertRaisesRegex(ServiceError, "missing"):
                read_key(path)
            open(path,"w").close()
            with self.assertRaisesRegex(ServiceError, "empty"):
                read_key(path)

    def test_invalid_key_contents_are_never_echoed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory,"key")
            secret = "PRIVATE INVALID KEY"
            with open(path,"w") as stream:
                stream.write(secret)
            try:
                read_key(path)
            except ServiceError as error:
                self.assertNotIn(secret, str(error))
            else:
                self.fail("Invalid key accepted")


if __name__ == "__main__":
    unittest.main()
