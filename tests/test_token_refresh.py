"""Tests for brand-scoped Meta token persistence and refresh.

Uses a temp SQLite file as the backing DB so we exercise the same code path
as production minus the Postgres vs SQLite dialect switch. That switch is
covered by the existing _add_column_if_missing / set_credential branches,
not re-tested here.
"""

import os
import tempfile
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class TokenRefreshTests(unittest.TestCase):
    def setUp(self):
        # Point the connection module at a fresh temp SQLite file and drop any
        # cached thread-local connection so each test starts clean.
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._prev_db_url = os.environ.pop("DATABASE_URL", None)
        self._prev_db_path = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = self._tmp.name

        from db import connection as conn_mod
        from db import schema as schema_mod

        conn_mod._local.__dict__.pop("connection", None)
        schema_mod._init_done = False
        schema_mod.init_db()
        self._conn_mod = conn_mod
        self._schema_mod = schema_mod

    def tearDown(self):
        self._conn_mod._local.__dict__.pop("connection", None)
        os.unlink(self._tmp.name)
        if self._prev_db_url is not None:
            os.environ["DATABASE_URL"] = self._prev_db_url
        if self._prev_db_path is not None:
            os.environ["DATABASE_PATH"] = self._prev_db_path
        else:
            os.environ.pop("DATABASE_PATH", None)
        self._schema_mod._init_done = False

    def test_credential_roundtrip(self):
        from tools.brand_credentials import get_credential, set_credential

        expires = datetime.now(timezone.utc) + timedelta(days=42)
        set_credential("mila", "META_ACCESS_TOKEN", "tok-abc", expires_at=expires)

        cred = get_credential("mila", "META_ACCESS_TOKEN")
        self.assertIsNotNone(cred)
        self.assertEqual(cred.value, "tok-abc")
        self.assertIsNotNone(cred.expires_at)
        self.assertEqual(get_credential("capa-co", "META_ACCESS_TOKEN"), None)

    def test_upsert_overwrites_existing(self):
        from tools.brand_credentials import get_credential, set_credential

        set_credential("mila", "META_ACCESS_TOKEN", "old")
        set_credential("mila", "META_ACCESS_TOKEN", "new")
        self.assertEqual(get_credential("mila", "META_ACCESS_TOKEN").value, "new")

    def test_expires_in_days_negative_when_expired(self):
        from tools.brand_credentials import credential_expires_in_days, set_credential

        past = datetime.now(timezone.utc) - timedelta(days=3)
        set_credential("mila", "META_ACCESS_TOKEN", "t", expires_at=past)
        self.assertLess(credential_expires_in_days("mila", "META_ACCESS_TOKEN"), 0)

    def test_expires_in_days_none_when_no_expiry_stored(self):
        from tools.brand_credentials import credential_expires_in_days, set_credential

        set_credential("mila", "META_ACCESS_TOKEN", "t", expires_at=None)
        self.assertIsNone(credential_expires_in_days("mila", "META_ACCESS_TOKEN"))

    def test_load_persisted_token_prefers_db_over_env(self):
        from tools.brand_credentials import set_credential
        from tools.token_refresh import load_persisted_token

        set_credential("mila", "META_ACCESS_TOKEN", "from-db")
        os.environ["META_ACCESS_TOKEN"] = "from-env"
        try:
            loaded = load_persisted_token("mila")
            self.assertTrue(loaded)
            self.assertEqual(os.environ["META_ACCESS_TOKEN"], "from-db")
        finally:
            os.environ.pop("META_ACCESS_TOKEN", None)

    def test_load_persisted_token_bootstrap_leaves_env_alone(self):
        from tools.token_refresh import load_persisted_token

        os.environ["META_ACCESS_TOKEN"] = "bootstrap"
        try:
            loaded = load_persisted_token("mila")
            self.assertFalse(loaded)
            self.assertEqual(os.environ["META_ACCESS_TOKEN"], "bootstrap")
        finally:
            os.environ.pop("META_ACCESS_TOKEN", None)

    def _set_app_creds(self):
        os.environ["META_APP_ID"] = "app-id"
        os.environ["META_APP_SECRET"] = "app-secret"

    def _clear_app_creds(self):
        os.environ.pop("META_APP_ID", None)
        os.environ.pop("META_APP_SECRET", None)

    def test_refresh_writes_new_token_and_expiry_to_db(self):
        from tools.brand_credentials import get_credential, set_credential
        from tools.token_refresh import refresh_meta_token

        set_credential("mila", "META_ACCESS_TOKEN", "old-token")
        self._set_app_creds()

        class FakeResp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"access_token": "new-token", "expires_in": 60 * 24 * 3600}

        captured = {}

        def fake_get(url, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return FakeResp()

        try:
            with patch("tools.token_refresh.requests.get", side_effect=fake_get):
                returned = refresh_meta_token("mila")
        finally:
            self._clear_app_creds()
            os.environ.pop("META_ACCESS_TOKEN", None)

        self.assertEqual(returned, "new-token")
        self.assertEqual(
            captured["url"], "https://graph.facebook.com/v21.0/oauth/access_token"
        )
        self.assertEqual(captured["params"]["grant_type"], "fb_exchange_token")
        self.assertEqual(captured["params"]["fb_exchange_token"], "old-token")
        self.assertEqual(captured["params"]["client_id"], "app-id")
        self.assertEqual(captured["params"]["client_secret"], "app-secret")
        cred = get_credential("mila", "META_ACCESS_TOKEN")
        self.assertEqual(cred.value, "new-token")
        self.assertIsNotNone(cred.expires_at)
        days = (cred.expires_at - datetime.now(timezone.utc)).days
        self.assertGreaterEqual(days, 58)
        self.assertLessEqual(days, 60)

    def test_refresh_raises_when_no_bootstrap_token(self):
        from tools.token_refresh import refresh_meta_token

        os.environ.pop("META_ACCESS_TOKEN", None)
        with self.assertRaises(RuntimeError):
            refresh_meta_token("mila")

    def test_refresh_raises_when_app_creds_missing(self):
        from tools.token_refresh import refresh_meta_token

        os.environ["META_ACCESS_TOKEN"] = "bootstrap-token"
        self._clear_app_creds()
        try:
            with self.assertRaises(RuntimeError):
                refresh_meta_token("mila")
        finally:
            os.environ.pop("META_ACCESS_TOKEN", None)

    def test_refresh_falls_back_to_default_ttl_when_api_omits_expires_in(self):
        from tools.brand_credentials import get_credential
        from tools.token_refresh import refresh_meta_token

        os.environ["META_ACCESS_TOKEN"] = "bootstrap-token"
        self._set_app_creds()

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"access_token": "new-token"}

        try:
            with patch("tools.token_refresh.requests.get", return_value=FakeResp()):
                refresh_meta_token("mila")
            cred = get_credential("mila", "META_ACCESS_TOKEN")
            self.assertIsNotNone(cred.expires_at)
            days = (cred.expires_at - datetime.now(timezone.utc)).days
            self.assertGreaterEqual(days, 58)
        finally:
            os.environ.pop("META_ACCESS_TOKEN", None)
            self._clear_app_creds()


class SetBrandHydrationTests(unittest.TestCase):
    """Regression tests for the Apr-2026 token expiry incident.

    ``set_brand()`` used to wipe os.environ back to the baseline host env and
    reapply the short-lived bootstrap ``MILA_META_ACCESS_TOKEN`` — silently
    clobbering the 60-day token that the scheduled refresh had written to the
    brand_credentials table. The result was that every scheduled task and
    health check hit Meta with an expired bootstrap even though the DB held
    a valid long-lived token. The hydration hook in set_brand closes that gap.
    """

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._prev_db_url = os.environ.pop("DATABASE_URL", None)
        self._prev_db_path = os.environ.get("DATABASE_PATH")
        os.environ["DATABASE_PATH"] = self._tmp.name

        from brands import loader as loader_mod
        from db import connection as conn_mod
        from db import schema as schema_mod

        conn_mod._local.__dict__.pop("connection", None)
        schema_mod._init_done = False
        schema_mod.init_db()

        # Reset the base-env snapshot so our injected env is treated as the
        # pristine host environment rather than leaking from an earlier test.
        loader_mod._BASE_ENV = None

        # Prevent a real ``brands/<slug>/.env`` (e.g. a dev checkout with
        # populated Meta credentials) from leaking a real token into the test
        # process via load_dotenv. We force env_path.exists() to False so the
        # loader skips the dotenv step entirely.
        self._exists_patcher = patch(
            "brands.loader.BrandConfig.env_path",
            new_callable=unittest.mock.PropertyMock,
        )
        mock_env_path = self._exists_patcher.start()
        mock_env_path.return_value = loader_mod.Path("/nonexistent/.env")

        self._conn_mod = conn_mod
        self._schema_mod = schema_mod
        self._loader_mod = loader_mod

    def tearDown(self):
        self._exists_patcher.stop()
        self._conn_mod._local.__dict__.pop("connection", None)
        os.unlink(self._tmp.name)
        if self._prev_db_url is not None:
            os.environ["DATABASE_URL"] = self._prev_db_url
        if self._prev_db_path is not None:
            os.environ["DATABASE_PATH"] = self._prev_db_path
        else:
            os.environ.pop("DATABASE_PATH", None)
        for k in ("META_ACCESS_TOKEN", "MILA_META_ACCESS_TOKEN"):
            os.environ.pop(k, None)
        self._schema_mod._init_done = False
        self._loader_mod._BASE_ENV = None

    def test_set_brand_hydrates_persisted_token_over_bootstrap(self):
        from brands.loader import set_brand
        from tools.brand_credentials import set_credential

        os.environ["MILA_META_ACCESS_TOKEN"] = "short-lived-bootstrap"
        set_credential("mila", "META_ACCESS_TOKEN", "long-lived-from-db")

        set_brand("mila")

        self.assertEqual(os.environ["META_ACCESS_TOKEN"], "long-lived-from-db")

    def test_set_brand_falls_through_to_bootstrap_when_db_empty(self):
        from brands.loader import set_brand

        os.environ["MILA_META_ACCESS_TOKEN"] = "bootstrap-only"

        set_brand("mila")

        self.assertEqual(os.environ["META_ACCESS_TOKEN"], "bootstrap-only")

    def test_set_brand_survives_missing_db(self):
        """Pre-init_db() contexts (main.py CLI) must not crash on set_brand."""
        from brands.loader import set_brand

        # Drop the creds table to simulate a pre-init_db state.
        self._conn_mod.get_db().execute("DROP TABLE brand_credentials")
        os.environ["MILA_META_ACCESS_TOKEN"] = "bootstrap"

        # Should not raise.
        set_brand("mila")
        self.assertEqual(os.environ["META_ACCESS_TOKEN"], "bootstrap")


if __name__ == "__main__":
    unittest.main()
