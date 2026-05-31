import unittest

from pipeline.web.app import SCREEN_ROUTES, create_app, render_shell


class OperationsWebAppShellTests(unittest.TestCase):
    def test_healthz_endpoint_is_registered(self) -> None:
        app = create_app()

        health_route = next((route for route in app.routes if getattr(route, "path", None) == "/healthz"), None)

        self.assertIsNotNone(health_route)
        self.assertEqual(health_route.endpoint(), {"status": "ok"})

    def test_shell_routes_render_navigation_placeholders(self) -> None:
        html = render_shell("/dashboard")

        for _, label in SCREEN_ROUTES:
            self.assertIn(label, html)

    def test_expected_placeholder_routes_are_registered(self) -> None:
        app = create_app()
        registered_paths = {route.path for route in app.routes if hasattr(route, "path")}

        self.assertIn("/", registered_paths)
        self.assertIn("/api/runs/submit", registered_paths)
        self.assertIn("/api/runs/active", registered_paths)
        self.assertIn("/api/runs/{request_id}", registered_paths)
        self.assertIn("/api/runs/{request_id}/cancel", registered_paths)
        for path, _ in SCREEN_ROUTES:
            self.assertIn(path, registered_paths)


if __name__ == "__main__":
    unittest.main()
