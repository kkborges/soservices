import argparse
import os
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


def _ts_dir() -> str:
    # Deterministic by date for easy diffs.
    return datetime.now().strftime("%Y-%m-%d")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_info(out_dir: Path, base_url: str, ui: str) -> None:
    (out_dir / "INFO.txt").write_text(
        "\n".join(
            [
                "LAS Platform - Marketing / Documentacao",
                f"base_url={base_url}",
                f"ui={ui}",
                f"captured_at={datetime.now().isoformat(timespec='seconds')}",
                "",
                "Obs: prints gerados via Playwright headless.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def capture(base_url: str, out_dir: Path, username: str, password: str, ui: str) -> None:
    _ensure_dir(out_dir)
    _write_info(out_dir, base_url, ui)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            locale="pt-BR",
        )
        context.add_init_script(
            f"localStorage.setItem('las_ui_version', {ui!r});"
        )
        page = context.new_page()

        def snap(name: str) -> None:
            page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True)

        # Login screen (sem credenciais visiveis)
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        try:
            page.fill('input[name=\"username\"]', "")
            page.fill('input[name=\"password\"]', "")
        except Exception:
            pass
        snap("01-login")

        # Autentica para navegar no app
        page.fill('input[name=\"username\"]', username)
        page.fill('input[name=\"password\"]', password)
        page.click("#login-form button[type=submit]")
        page.wait_for_selector("#app-screen:not(.hidden)", timeout=60_000)
        page.wait_for_timeout(800)

        # Dashboard
        snap("02-home")

        def go_view(view: str, shot_name: str, wait_selector: str | None = None) -> None:
            page.click(f'button.nav-link[data-view=\"{view}\"]')
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=30_000)
            page.wait_for_timeout(900)
            snap(shot_name)

        # Lists
        go_view("hosts", "03-hosts", "article.card")
        # Host detail (se existir)
        if page.locator(".host-detail-trigger").count() > 0:
            page.click(".host-detail-trigger")
            page.wait_for_selector(".entity-detail", timeout=30_000)
            page.wait_for_timeout(800)
            snap("04-host-detail")
            # Volta para hosts, se houver botao
            if page.locator("#back-hosts").count() > 0:
                page.click("#back-hosts")
                page.wait_for_timeout(600)

        go_view("processes", "05-processes", "article.card")
        go_view("services", "06-services", "article.card")
        go_view("applications", "07-applications", "article.card")
        go_view("topologies", "08-topologies", "article.card")
        go_view("logs", "09-logs", "article.card")
        go_view("traces", "10-traces", "article.card")
        go_view("synthetics", "11-synthetics", "article.card")
        go_view("tickets", "12-tickets", "article.card")
        go_view("integrations", "13-integrations", "article.card")
        go_view("network", "14-network-assets", "article.card")
        go_view("security", "15-security", "article.card")
        go_view("settings", "16-settings", "article.card")

        # API docs (Swagger / OpenAPI)
        page.goto(f"{base_url}/api/docs", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        snap("17-api-docs")

        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Captura prints das telas da plataforma LAS (para docs/pitch/marketing)."
    )
    parser.add_argument("--base-url", default=os.getenv("LAS_BASE_URL", "http://las.soservices.com.br"))
    parser.add_argument("--username", default=os.getenv("LAS_USER", ""))
    parser.add_argument("--password", default=os.getenv("LAS_PASS", ""))
    parser.add_argument("--ui", choices=["classic", "v2"], default=os.getenv("LAS_UI", "v2"))
    parser.add_argument(
        "--out",
        default=str(Path("docs") / "marketing" / "screenshots" / _ts_dir()),
        help="Diretorio de saida (default: docs/marketing/screenshots/YYYY-MM-DD).",
    )
    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit(
            "Credenciais ausentes. Use --username/--password ou defina LAS_USER e LAS_PASS."
        )

    capture(
        base_url=args.base_url.rstrip("/"),
        out_dir=Path(args.out),
        username=args.username,
        password=args.password,
        ui=args.ui,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
