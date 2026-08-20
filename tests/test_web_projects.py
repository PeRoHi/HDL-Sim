"""Legacy /api/projects is removed; UI uses .spj instead."""

from hdl_sim.web.app import create_app


def test_legacy_projects_api_is_gone() -> None:
    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/projects" not in paths
    assert "/api/projects/{project_name}" not in paths
