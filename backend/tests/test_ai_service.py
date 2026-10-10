import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from app.database import db
from app.config import Config
from app.services.gemini_service import (
    GeminiService,
    AIServiceError,
    AIConfigurationError,
    AIRateLimitError,
    AITimeoutError,
    AIProviderError,
    AIValidationError,
    STANDARD_SAFETY_WARNING
)
from app.utils.security import create_access_token


@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "STORAGE_DIR": tmp_path / "storage"
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client


@pytest.fixture
def auth_header():
    """Generate a valid Authorization header for testing protected routes."""
    token = create_access_token(user_id=1, email="test@example.com")
    return {"Authorization": f"Bearer {token}"}


class TestGeminiServiceUnit:
    """Unit tests for GeminiService logic, validation, and JSON parsing."""

    def test_validation_empty_input(self):
        with pytest.raises(AIValidationError) as exc:
            GeminiService.explain_code("")
        assert "cannot be empty" in str(exc.value)

    def test_validation_whitespace_only(self):
        with pytest.raises(AIValidationError) as exc:
            GeminiService.generate_code("   ")
        assert "cannot be empty" in str(exc.value)

    def test_validation_exceeds_max_length(self):
        huge_code = "x = 1\n" * 15000  # > 50,000 chars
        with pytest.raises(AIValidationError) as exc:
            GeminiService.explain_code(huge_code)
        assert "exceeds maximum allowed length" in str(exc.value)

    def test_is_configured(self):
        with patch.object(Config, "GEMINI_API_KEY", ""):
            assert GeminiService.is_configured() is False
        with patch.object(Config, "GEMINI_API_KEY", "your_gemini_api_key_here"):
            assert GeminiService.is_configured() is False
        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            assert GeminiService.is_configured() is True

    def test_unconfigured_service_raises_error(self):
        with patch.object(Config, "GEMINI_API_KEY", ""):
            with pytest.raises(AIConfigurationError):
                GeminiService.explain_code("def add(a, b): return a + b")

    def test_parse_valid_json_response(self):
        raw_json = (
            '{\n'
            '  "summary": "Calculates the sum of two numbers.",\n'
            '  "code": null,\n'
            '  "assumptions_warnings": ["Assumes numerical arguments."],\n'
            '  "improvements": ["Add type hints."]\n'
            '}'
        )
        parsed = GeminiService._parse_and_validate_response(raw_json, "explain", "gemini-2.5-flash")
        assert parsed["success"] is True
        assert parsed["operation"] == "explain"
        assert parsed["summary"] == "Calculates the sum of two numbers."
        assert parsed["code"] is None
        assert "Assumes numerical arguments." in parsed["assumptions_warnings"]
        assert any("AI-generated" in w for w in parsed["assumptions_warnings"])
        assert "Add type hints." in parsed["improvements"]
        assert parsed["model"] == "gemini-2.5-flash"

    def test_parse_markdown_wrapped_json_response(self):
        raw = (
            '```json\n'
            '{\n'
            '  "summary": "Fixes null pointer exception.",\n'
            '  "code": "if user is not None: return user.name",\n'
            '  "assumptions_warnings": ["User object may be None."],\n'
            '  "improvements": ["Use optional chaining."]\n'
            '}\n'
            '```'
        )
        parsed = GeminiService._parse_and_validate_response(raw, "debug", "gemini-2.5-flash")
        assert parsed["success"] is True
        assert parsed["operation"] == "debug"
        assert "Fixes null pointer" in parsed["summary"]
        assert "if user is not None" in parsed["code"]

    def test_parse_malformed_non_json_response_resilience(self):
        raw = "This is a plain text response without JSON markup from the model."
        parsed = GeminiService._parse_and_validate_response(raw, "explain", "gemini-2.5-flash")
        assert parsed["success"] is True
        assert parsed["operation"] == "explain"
        assert parsed["summary"] == "This is a plain text response without JSON markup from the model."
        assert parsed["code"] is None
        assert len(parsed["assumptions_warnings"]) > 0  # Standard safety warning added


class TestAIRoutes:
    """Integration tests for /api/v1/ai REST endpoints."""

    def test_get_ai_status(self, client):
        res = client.get("/api/v1/ai/status")
        assert res.status_code == 200
        data = res.get_json()
        assert "configured" in data
        assert "model" in data
        assert data["provider"] == "google-genai"
        assert "operations" in data

    def test_explain_unauthenticated(self, client):
        res = client.post("/api/v1/ai/explain", json={"code": "print('hello')"})
        assert res.status_code == 401

    def test_debug_unauthenticated(self, client):
        res = client.post("/api/v1/ai/debug", json={"code": "print('hello')"})
        assert res.status_code == 401

    def test_generate_unauthenticated(self, client):
        res = client.post("/api/v1/ai/generate", json={"prompt": "create a function"})
        assert res.status_code == 401

    def test_improve_unauthenticated(self, client):
        res = client.post("/api/v1/ai/improve", json={"code": "print('hello')"})
        assert res.status_code == 401

    def test_explain_validation_error_missing_code(self, client, auth_header):
        res = client.post("/api/v1/ai/explain", json={}, headers=auth_header)
        assert res.status_code == 400
        assert "code" in res.get_json()["error"]

    def test_generate_validation_error_missing_prompt(self, client, auth_header):
        res = client.post("/api/v1/ai/generate", json={}, headers=auth_header)
        assert res.status_code == 400
        assert "prompt" in res.get_json()["error"]

    def test_explain_code_success_mocked(self, client, auth_header):
        mock_response = MagicMock()
        mock_response.text = (
            '{\n'
            '  "summary": "This function authenticates a user by checking their password hash.",\n'
            '  "code": null,\n'
            '  "assumptions_warnings": ["Assumes bcrypt is installed."],\n'
            '  "improvements": ["Add rate limiting."]\n'
            '}'
        )

        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.models.generate_content.return_value = mock_response
                mock_get_client.return_value = mock_client

                res = client.post(
                    "/api/v1/ai/explain",
                    json={
                        "code": "def check_pw(pw, hash): return bcrypt.verify(pw, hash)",
                        "language": "python",
                        "file_path": "auth.py"
                    },
                    headers=auth_header
                )

                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["operation"] == "explain"
                assert "authenticates a user" in data["summary"]
                assert data["code"] is None
                assert "Add rate limiting." in data["improvements"]

    def test_debug_code_success_mocked(self, client, auth_header):
        mock_response = MagicMock()
        mock_response.text = (
            '{\n'
            '  "summary": "Root cause is ZeroDivisionError when count is 0.",\n'
            '  "code": "def avg(items):\\n    return sum(items) / len(items) if items else 0",\n'
            '  "assumptions_warnings": ["Returns 0 for empty list."],\n'
            '  "improvements": ["Add type annotations."]\n'
            '}'
        )

        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.models.generate_content.return_value = mock_response
                mock_get_client.return_value = mock_client

                res = client.post(
                    "/api/v1/ai/debug",
                    json={
                        "code": "def avg(items): return sum(items) / len(items)",
                        "error_message": "ZeroDivisionError: division by zero",
                        "language": "python"
                    },
                    headers=auth_header
                )

                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["operation"] == "debug"
                assert "ZeroDivisionError" in data["summary"]
                assert "if items else 0" in data["code"]

    def test_generate_code_success_mocked(self, client, auth_header):
        mock_response = MagicMock()
        mock_response.text = (
            '{\n'
            '  "summary": "Creates an Express rate-limiting middleware using token bucket.",\n'
            '  "code": "const rateLimit = require(\'express-rate-limit\');\\nmodule.exports = rateLimit({ windowMs: 60000, max: 100 });",\n'
            '  "assumptions_warnings": ["Requires express-rate-limit package."],\n'
            '  "improvements": ["Use Redis for distributed stores."]\n'
            '}'
        )

        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.models.generate_content.return_value = mock_response
                mock_get_client.return_value = mock_client

                res = client.post(
                    "/api/v1/ai/generate",
                    json={
                        "prompt": "Create an Express rate limiter middleware allowing 100 requests per minute",
                        "language": "javascript"
                    },
                    headers=auth_header
                )

                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["operation"] == "generate"
                assert "express-rate-limit" in data["code"]

    def test_improve_code_success_mocked(self, client, auth_header):
        mock_response = MagicMock()
        mock_response.text = (
            '{\n'
            '  "summary": "Optimized lookup from O(N) to O(1) by using a set.",\n'
            '  "code": "seen = set(items)\\ndef has_item(x): return x in seen",\n'
            '  "assumptions_warnings": ["Items must be hashable."],\n'
            '  "improvements": ["Freeze set if immutable."]\n'
            '}'
        )

        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.models.generate_content.return_value = mock_response
                mock_get_client.return_value = mock_client

                res = client.post(
                    "/api/v1/ai/improve",
                    json={
                        "code": "def has_item(x, items): return x in items",
                        "focus": "performance",
                        "language": "python"
                    },
                    headers=auth_header
                )

                assert res.status_code == 200
                data = res.get_json()
                assert data["success"] is True
                assert data["operation"] == "improve"
                assert "set(items)" in data["code"]

    def test_rate_limit_error_handling(self, client, auth_header):
        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")
                mock_get_client.return_value = mock_client

                res = client.post(
                    "/api/v1/ai/explain",
                    json={"code": "def f(): pass"},
                    headers=auth_header
                )
                assert res.status_code == 429
                assert "quota exceeded" in res.get_json()["error"].lower()

    def test_timeout_error_handling(self, client, auth_header):
        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.models.generate_content.side_effect = Exception("Request timed out after 45s")
                mock_get_client.return_value = mock_client

                res = client.post(
                    "/api/v1/ai/explain",
                    json={"code": "def f(): pass"},
                    headers=auth_header
                )
                assert res.status_code == 504
                assert "timed out" in res.get_json()["error"].lower()

    def test_provider_error_handling(self, client, auth_header):
        with patch.object(Config, "GEMINI_API_KEY", "AIzaSyFakeKeyTest123456"):
            with patch("app.services.gemini_service.GeminiService.get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.models.generate_content.side_effect = Exception("500 Internal Server Error in upstream cluster")
                mock_get_client.return_value = mock_client

                res = client.post(
                    "/api/v1/ai/explain",
                    json={"code": "def f(): pass"},
                    headers=auth_header
                )
                assert res.status_code == 502
                assert "gemini service error" in res.get_json()["error"].lower()

    def test_missing_gemini_key_returns_503(self, client, auth_header):
        with patch.object(Config, "GEMINI_API_KEY", ""):
            res = client.post(
                "/api/v1/ai/explain",
                json={"code": "def f(): pass"},
                headers=auth_header
            )
            assert res.status_code == 503
            assert "gemini_not_configured" in res.get_json()["error_code"]
