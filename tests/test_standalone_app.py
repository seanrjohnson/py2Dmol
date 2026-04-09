from __future__ import annotations

from pathlib import Path


def _enable_msa_loading(page) -> None:
    page.evaluate(
        """
        () => {
            const el = document.getElementById('loadMSACheckbox');
            if (el && !el.checked) {
                el.checked = true;
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        """
    )


def _load_entropy_ready_example(page, served_dist_url: str) -> None:
    page.goto(f"{served_dist_url}/index.html", wait_until="domcontentloaded", timeout=120000)
    _enable_msa_loading(page)
    page.locator('[data-example-value="Q5VSL9"]').click()
    page.wait_for_function(
        """
        () => {
            const viewerId = window.viewerConfig && window.viewerConfig.viewer_id;
            const renderer = viewerId && window.py2dmol_viewers && window.py2dmol_viewers[viewerId]
                ? window.py2dmol_viewers[viewerId].renderer
                : null;
            const option = document.getElementById('entropyColorOption');
            return !!(
                renderer &&
                renderer.currentObjectName &&
                Array.isArray(renderer.entropy) &&
                renderer.entropy.some(v => v !== undefined && v >= 0) &&
                option &&
                !option.hidden
            );
        }
        """,
        timeout=180000,
    )


def test_standalone_index_loads(page, served_dist_url: str) -> None:
    page.goto(f"{served_dist_url}/index.html", wait_until="domcontentloaded", timeout=120000)

    assert page.title() == "2Dmol"
    assert page.locator("#fetch-btn").is_visible()
    assert page.locator("#upload-button").is_visible()
    assert page.locator("#exportEntropyTsvButton").count() == 1


def test_export_tsv_preserves_entropy_state(page, served_dist_url: str) -> None:
    _load_entropy_ready_example(page, served_dist_url)
    page.locator("#colorSelect").select_option("auto")

    before = page.evaluate(
        """
        () => {
            const viewerId = window.viewerConfig.viewer_id;
            const renderer = window.py2dmol_viewers[viewerId].renderer;
            const option = document.getElementById('entropyColorOption');
            return {
                colorMode: renderer.colorMode,
                entropyPresent: Array.isArray(renderer.entropy) && renderer.entropy.some(v => v !== undefined && v >= 0),
                entropyLength: Array.isArray(renderer.entropy) ? renderer.entropy.length : null,
                entropyOptionHidden: option ? option.hidden : null,
            };
        }
        """
    )

    with page.expect_download(timeout=120000) as download_info:
        page.locator("#exportEntropyTsvButton").click()
    download = download_info.value
    download_path = download.path()

    after = page.evaluate(
        """
        () => {
            const viewerId = window.viewerConfig.viewer_id;
            const renderer = window.py2dmol_viewers[viewerId].renderer;
            const option = document.getElementById('entropyColorOption');
            return {
                colorMode: renderer.colorMode,
                entropyPresent: Array.isArray(renderer.entropy) && renderer.entropy.some(v => v !== undefined && v >= 0),
                entropyLength: Array.isArray(renderer.entropy) ? renderer.entropy.length : null,
                entropyOptionHidden: option ? option.hidden : null,
                status: document.getElementById('status-message')?.textContent || '',
            };
        }
        """
    )

    assert before["colorMode"] == "auto"
    assert before["entropyPresent"] is True
    assert before["entropyOptionHidden"] is False
    assert download_path is not None and Path(download_path).exists()
    assert after["colorMode"] == "auto"
    assert after["entropyPresent"] is True
    assert after["entropyOptionHidden"] is False
    assert after["entropyLength"] == before["entropyLength"]
    assert "Exported TSV:" in after["status"]


def test_structure_hover_updates_sequence_hover_state(page, served_dist_url: str) -> None:
    page.goto(f"{served_dist_url}/index.html", wait_until="domcontentloaded", timeout=120000)
    page.locator('[data-example-value="4HHB"]').click()

    page.wait_for_function(
        """
        () => {
            const viewerId = window.viewerConfig && window.viewerConfig.viewer_id;
            const renderer = viewerId && window.py2dmol_viewers && window.py2dmol_viewers[viewerId]
                ? window.py2dmol_viewers[viewerId].renderer
                : null;
            const sequenceCanvas = document.getElementById('sequenceCanvas');
            return !!(
                renderer &&
                renderer.currentObjectName &&
                sequenceCanvas &&
                renderer.screenValid &&
                renderer.screenX &&
                renderer.screenY &&
                renderer.screenValid.some(v => v === renderer.screenFrameId)
            );
        }
        """,
        timeout=180000,
    )

    hover_target = page.evaluate(
        """
        () => {
            const viewerId = window.viewerConfig.viewer_id;
            const renderer = window.py2dmol_viewers[viewerId].renderer;
            const validFrameId = renderer.screenFrameId;

            for (let idx = 0; idx < renderer.screenValid.length; idx++) {
                if (renderer.screenValid[idx] !== validFrameId) continue;
                return {
                    index: idx,
                    x: renderer.screenX[idx],
                    y: renderer.screenY[idx],
                    chain: renderer.chains[idx],
                    resSeq: renderer.residueNumbers[idx],
                };
            }
            return null;
        }
        """
    )

    assert hover_target is not None

    page.locator("#canvas").hover(position={"x": hover_target["x"], "y": hover_target["y"]})

    page.wait_for_function(
        """
        (expected) => {
            const state = window.SEQ && window.SEQ.getExternalHoverState
                ? window.SEQ.getExternalHoverState()
                : null;
            const viewerId = window.viewerConfig && window.viewerConfig.viewer_id;
            const renderer = viewerId && window.py2dmol_viewers && window.py2dmol_viewers[viewerId]
                ? window.py2dmol_viewers[viewerId].renderer
                : null;
            return !!(
                state &&
                state.positionIndex === expected.index &&
                state.chainId === expected.chain &&
                renderer &&
                renderer.highlightedAtom === expected.index
            );
        }
        """,
        arg=hover_target,
        timeout=30000,
    )

    tooltip_lines = page.evaluate(
        """
        () => window.SEQ.getHoveredTooltipLines()
        """
    )

    hovered_state = page.evaluate(
        """
        () => window.SEQ.getExternalHoverState()
        """
    )

    assert hovered_state["positionIndex"] == hover_target["index"]
    assert hovered_state["chainId"] == hover_target["chain"]
    assert hovered_state["hoveredResidueInfo"]["positionIndex"] == hover_target["index"]
    assert f"Pos: {hover_target['resSeq']}" in tooltip_lines
    assert f"Index: {hover_target['index']}" in tooltip_lines
    assert f"Index: {hover_target['resSeq']}" not in tooltip_lines

    page.evaluate(
        """
        () => {
            const canvas = document.getElementById('canvas');
            canvas.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
        }
        """
    )

    page.wait_for_function(
        """
        () => {
            const state = window.SEQ && window.SEQ.getExternalHoverState
                ? window.SEQ.getExternalHoverState()
                : null;
            const viewerId = window.viewerConfig && window.viewerConfig.viewer_id;
            const renderer = viewerId && window.py2dmol_viewers && window.py2dmol_viewers[viewerId]
                ? window.py2dmol_viewers[viewerId].renderer
                : null;
            return !!(
                state &&
                state.positionIndex === null &&
                state.chainId === null &&
                state.hoveredResidueInfo === null &&
                renderer &&
                renderer.highlightedAtom === null &&
                renderer.highlightedAtoms === null
            );
        }
        """,
        timeout=30000,
    )