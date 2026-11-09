"""Exercise the real local app in Chromium, including a generated RTL download.

Install the optional Playwright check dependency and Chromium first. Neither is
needed to launch the app in an ordinary browser. All requests stay on loopback.
"""

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import zipfile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.server import EditorServer


def run(output, *, run_pyuvm=False):
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory() as directory:
        server = EditorServer(("127.0.0.1", 0), directory)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda msg: errors.append(msg.text)
                        if msg.type == "error" and not (
                            msg.location.get("url", "").endswith("/api/parse") and
                            "422" in msg.text) else None)
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator("#validation-status")).to_have_text("Layout is valid")
                expect(page.locator(".tile-cell")).to_have_count(4)
                for kind in ("BCT", "MST", "VCT", "SFT", "CPT"):
                    expect(page.get_by_role("button", name=f"Place {kind}", exact=True)).to_be_enabled()

                # Help explains current geometry and never edits the architecture.
                expect(page.locator("#grid-impact")).to_contain_text("4 native tiles")
                expect(page.locator("#grid-impact")).to_contain_text("4 neighbor links")
                expect(page.locator("#memory-impact")).to_contain_text("65536 bytes total")
                expect(page.locator("#guidance-scope")).to_contain_text("qualitative")
                assert page.locator("#guidance-scope").bounding_box()["y"] >= (
                    page.locator(".design-heading").bounding_box()["y"] +
                    page.locator(".design-heading").bounding_box()["height"])
                draft = page.evaluate("localStorage.getItem('mosaic.flavor-studio.draft.v1')")
                grid_help = page.locator("#grid-guidance details")
                grid_help.locator("summary").focus()
                page.keyboard.press("Enter")
                expect(grid_help).to_have_attribute("open", "")
                expect(grid_help).to_contain_text("Manhattan distance")
                self_help = page.locator('details[data-help-key="tile:BCT"]')
                self_help.locator("summary").click()
                expect(self_help).to_contain_text("DATA_WIDTH")
                assert page.evaluate("localStorage.getItem('mosaic.flavor-studio.draft.v1')") == draft
                # Open explanations survive changing the associated setting.
                latency = page.locator("#parameter-ALU_LATENCY-implications")
                latency.locator("summary").click()
                expect(latency).to_contain_text("does not itself split the arithmetic critical path")
                page.locator("#parameter-ALU_LATENCY").select_option("0")
                expect(latency).to_have_attribute("open", "")
                page.locator("#parameter-ALU_LATENCY").select_option("1")

                # Edits belong to one tile and survive undo/redo and a reload.
                page.locator("#parameter-RF_DEPTH").select_option("16")
                page.locator("#tile-slot-0-1").click()
                expect(page.locator("#parameter-RF_DEPTH")).to_have_value("8")
                page.locator("#undo-button").click()
                page.locator("#tile-slot-0-0").click()
                expect(page.locator("#parameter-RF_DEPTH")).to_have_value("8")
                page.locator("#redo-button").click()
                expect(page.locator("#parameter-RF_DEPTH")).to_have_value("16")
                page.reload()
                expect(page.locator("#parameter-RF_DEPTH")).to_have_value("16")
                page.locator("#tile-id").fill("")
                page.locator("#tile-id").press("Tab")
                expect(page.locator("#validation-status")).to_have_text("Layout needs attention")
                page.locator("#undo-button").click()

                # Real drag/drop preserves tile identities and their private knobs.
                page.locator("#tile-slot-0-0").drag_to(page.locator("#tile-slot-0-1"))
                expect(page.locator("#tile-slot-0-1")).to_contain_text("TILE 00")
                expect(page.locator("#parameter-RF_DEPTH")).to_have_value("16")
                page.locator("#undo-button").click()

                # Every class is selectable. Zero/multiple MSTs are supported.
                page.locator("#tile-slot-0-1").click()
                for kind in ("VCT", "CPT", "SFT"):
                    page.locator("#tile-class").select_option(kind)
                    expect(page.locator("#tile-class")).to_have_value(kind)
                    expect(page.locator("#validation-status")).to_have_text("Layout is valid")
                    if kind == "VCT":
                        page.locator("#parameter-NUM_LANES").select_option("8")
                        expect(page.locator("#parameter-NUM_LANES-effect")).to_contain_text("256 native payload bits")
                        expect(page.locator("#summary-data-width")).to_have_text("256")
                        page.locator("#parameter-NUM_LANES").select_option("4")
                    if kind == "CPT":
                        page.locator("#parameter-EVENT_COUNT_WIDTH").select_option("2")
                        expect(page.locator("#parameter-EVENT_COUNT_WIDTH-effect")).to_have_text("Unsigned count range: 0 to 3.")
                page.locator("#parameter-INPUT_FRAC_BITS").select_option("12")
                expect(page.locator("#parameter-INPUT_FRAC_BITS-effect")).to_contain_text("0.000244141")
                reciprocal_help = page.locator("#fu-help-ENABLE_RECIPROCAL")
                reciprocal_help.locator("summary").click()
                expect(reciprocal_help).to_contain_text("Reciprocal contexts are rejected")
                page.get_by_role("checkbox", name="Enable Exponential", exact=True).check()
                page.locator("#parameter-EXP_PIPELINE_DEPTH").select_option("7")
                # Enabling exp must not enable either normalization FU.
                expect(page.get_by_role("checkbox", name="Enable Reciprocal", exact=True)).not_to_be_checked()
                expect(page.get_by_role("checkbox", name="Enable RSQRT", exact=True)).not_to_be_checked()
                page.get_by_role("checkbox", name="Enable Reciprocal", exact=True).check()
                expect(reciprocal_help).to_have_attribute("open", "")
                expect(reciprocal_help).to_contain_text("Enables reciprocal independently")
                page.get_by_role("checkbox", name="Enable Polynomial", exact=True).uncheck()
                page.locator("#parameter-RECIP_INTERNAL_WIDTH").select_option("32")
                expect(page.get_by_role("checkbox", name="Enable Reciprocal", exact=True)).to_be_checked()
                expect(page.get_by_role("checkbox", name="Enable Polynomial", exact=True)).not_to_be_checked()
                expect(page.get_by_role("checkbox", name="Enable RSQRT", exact=True)).not_to_be_checked()
                page.locator("#tile-slot-0-0").click()
                expect(page.locator("#parameter-RF_DEPTH")).to_have_value("16")
                page.get_by_role("button", name="Place MST", exact=True).click()
                page.locator("#tile-slot-0-0").click()
                expect(page.locator("#validation-status")).to_have_text("Layout is valid")
                expect(page.locator("#summary-memory")).to_have_text("2")
                page.keyboard.press("Escape")
                page.locator("#undo-button").click()
                expect(page.locator("#validation-status")).to_have_text("Layout is valid")

                page.locator("#grid-rows").fill("3")
                page.locator("#grid-rows").press("Tab")
                page.locator("#grid-cols").fill("5")
                page.locator("#grid-cols").press("Tab")
                expect(page.locator(".tile-cell")).to_have_count(15)
                expect(page.locator("#validation-status")).to_have_text("Layout is valid")
                for name in ("grid-rows", "grid-cols"):
                    page.locator("#" + name).fill("2")
                    page.locator("#" + name).press("Tab")
                expect(page.locator(".tile-cell")).to_have_count(4)

                # Bad TOML leaves the current architecture intact. Valid source
                # changes use exactly the same model as the visual controls.
                page.locator("#toml-tab").click()
                expect(page.locator("#toml-source")).to_have_value(re.compile("mosaic-flavor-v1"))
                source = page.locator("#toml-source").input_value()
                page.locator("#toml-source").fill("[broken")
                page.locator("#apply-toml").click()
                expect(page.locator("#toast-region")).to_contain_text("Expected")
                expect(page.locator("#generate-button")).to_be_disabled()
                page.locator("#toml-source").fill(source.replace('"my_cgra"', '"browser_flavor"'))
                page.locator("#apply-toml").click()
                expect(page.locator("#flavor-name")).to_have_value("browser_flavor")
                expect(page.locator("#generate-button")).to_be_enabled()

                with page.expect_download() as download:
                    page.locator("#save-button").click()
                toml = output / "browser_flavor.toml"
                download.value.save_as(toml)
                page.locator("#file-input").set_input_files(toml)
                expect(page.locator("#flavor-name")).to_have_value("browser_flavor")
                expect(page.locator("#generate-button")).to_be_enabled()
                page.locator("#layout-tab").click()
                page.locator("#generate-button").click()
                expect(page.locator(".job-card.succeeded")).to_have_count(1, timeout=30000)
                with page.expect_download() as download:
                    page.get_by_role("link", name="Download RTL").click()
                export = output / "browser_flavor.zip"
                download.value.save_as(export)
                with zipfile.ZipFile(export) as archive:
                    assert ".RF_DEPTH(16)" in archive.read("rtl/cluster.sv").decode()
                    assert json.loads(archive.read("generation.json"))["name"] == "browser_flavor"

                if run_pyuvm:
                    page.locator("#simulator").select_option("icarus")
                    expect(page.locator("#test-button")).to_be_enabled()
                    page.locator("#test-button").click()
                    expect(page.locator(".job-card.succeeded")).to_have_count(2, timeout=1800000)
                    expect(page.locator("#jobs-list")).to_contain_text("Python/PyUVM passed")

                page.reload()
                expect(page.locator(".job-card.succeeded")).to_have_count(2 if run_pyuvm else 1)
                expect(page.locator("#jobs-list")).to_contain_text("Restored job")
                expect(page.locator("#validation-status")).to_have_text("Layout is valid")

                page.screenshot(path=output / "desktop.png", full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.locator("#tile-slot-1-1").click()
                expect(page.locator("#tile-class")).to_have_value("MST")
                expect(page.locator('#parameter-SUPPORT_CIRCULAR option[value="1"]')).to_be_disabled()
                page.locator("#parameter-SUPPORT_WIDTH_CONVERSION-implications summary").click()
                expect(page.locator("#parameter-SUPPORT_WIDTH_CONVERSION-implications")).to_contain_text("must remain enabled")
                page.screenshot(path=output / "mobile.png", full_page=True)
                assert not errors, errors
                # A server started before this feature needs a clear, draft-safe restart path.
                draft = page.evaluate("localStorage.getItem('mosaic.flavor-studio.draft.v1')")
                def old_catalog(route):
                    response = route.fetch()
                    payload = response.json()
                    payload.pop("configuration_guidance", None)
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
                page.route("**/api/catalog", old_catalog)
                page.reload()
                expect(page.locator("#startup-error-message")).to_contain_text("Restart the local app server")
                assert page.evaluate("localStorage.getItem('mosaic.flavor-studio.draft.v1')") == draft
                page.unroute("**/api/catalog", old_catalog)
                page.locator("#retry-button").click()
                expect(page.locator("#validation-status")).to_have_text("Layout is valid")
                expect(page.locator("#flavor-name")).to_have_value("browser_flavor")
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    print(f"Browser workflow PASS; screenshots and downloads: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/app-checks/browser")
    parser.add_argument("--run-pyuvm", action="store_true",
                        help="Also run the actual 2×2 PyUVM job from the browser")
    args = parser.parse_args()
    run(args.output.resolve(), run_pyuvm=args.run_pyuvm)
