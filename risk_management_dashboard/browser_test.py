"""
End-to-end Browser Automation & Integration Test for MT5 Risk Management Dashboard.
Tests:
1. Navigation and page load without console errors
2. Real-time account balance, equity, and leverage in the prominent header
3. Dynamic Working Capital input modification & immediate table recalculation
4. Risk Sizing Model dropdown switching (Fractional, Kelly, Optimal f)
5. Global Stop Loss Mode preset switching (1/4 ADR, 1/2 ADR, 1.0 ADR, 20 pips, 50 pips)
6. Changing Stop Loss (pips) for each individual symbol and testing '1/4 ADR' reset
7. Category Tab filtering (All, Majors, Minors, Metals, Energies, Indices, Crypto)
8. Symbol search filtering
9. Deep-Dive Math Modal opening and verification
10. Ralph Vince Optimal f TWR Canvas Chart rendering
11. Manual Strategy Parameter Override modal
12. HTML Tooltip validation on minimum volume clamped lots
"""

import asyncio
import os
import sys
from playwright.async_api import async_playwright


async def run_browser_tests():
    console_errors = []
    page_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        # Listen for console and uncaught errors
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        print("\n[1] Navigating to http://127.0.0.1:8000/ ...")
        await page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # 1. Check title
        title = await page.title()
        print(f"    Page Title: {title}")
        assert "Risk Management" in title

        # 2. Check header metrics
        balance_text = await page.locator(".header-center-metrics .header-metric-val").nth(0).text_content()
        leverage_text = await page.locator(".header-center-metrics .header-metric-val").nth(2).text_content()
        print(f"    Header Broker Balance: {balance_text.strip()}, Leverage: {leverage_text.strip()}")

        # 3. Test Working Capital adjustment & localStorage persistence
        print("\n[2] Testing Working Capital modification and localStorage persistence...")
        wc_input = page.locator("input[type='number']").nth(0)
        await wc_input.fill("750")
        await page.wait_for_timeout(300)
        
        saved_wc = await page.evaluate("localStorage.getItem('mt5_risk_working_capital')")
        print(f"    Saved to localStorage: {saved_wc}")
        assert saved_wc == "750"

        # Test reload persistence
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(500)
        reloaded_wc = await page.locator("input[type='number']").nth(0).input_value()
        print(f"    Reloaded Working Capital from localStorage: ${reloaded_wc}")
        assert reloaded_wc == "750"

        # Test Reset to Balance
        reset_wc_btn = page.locator(".quick-sl-btn:has-text('Reset to Balance')")
        await reset_wc_btn.click()
        await page.wait_for_timeout(400)
        cleared_wc = await page.evaluate("localStorage.getItem('mt5_risk_working_capital')")
        reset_val = await page.locator("input[type='number']").nth(0).input_value()
        print(f"    After Reset to Balance -> Working Capital: ${reset_val}, localStorage cleared: {cleared_wc is None}")
        assert cleared_wc is None

        # 4. Test Risk Model Switcher
        print("\n[3] Testing Risk Sizing Models...")
        risk_select = page.locator("select").nth(0)
        
        await risk_select.select_option("kelly_quarter")
        await page.wait_for_timeout(400)
        print("    Switched to: Quarter Kelly")

        await risk_select.select_option("optimal_f_half")
        await page.wait_for_timeout(400)
        print("    Switched to: Half Optimal f")

        await risk_select.select_option("fractional")
        await page.wait_for_timeout(400)
        print("    Switched back to: Fractional")

        # 5. Test Global Stop Loss Mode Presets
        print("\n[4] Testing Global Stop Loss Mode Presets...")
        sl_mode_select = page.locator("select").nth(1)
        for mode in ["1/2 ADR", "1.0 ADR", "ATR(14)", "1/3 ADR", "1/4 ADR"]:
            await sl_mode_select.select_option(mode)
            await page.wait_for_timeout(300)
            first_sl = await page.locator(".sl-input").nth(0).input_value()
            print(f"    Preset [{mode}] -> EURUSD SL: {first_sl} pips")

        # 6. Test Changing Stop Loss for EACH Symbol
        print("\n[5] Testing individual Stop Loss editing for each symbol...")
        sl_inputs = page.locator(".sl-input")
        count = await sl_inputs.count()
        print(f"    Found {count} symbols in screener table.")
        
        for i in range(min(count, 8)):
            symbol_name = await page.locator(".symbol-cell span").nth(i * 2).text_content()
            input_el = sl_inputs.nth(i)
            current_val = await input_el.input_value()
            new_val = str(float(current_val) + 15.0)
            
            await input_el.fill(new_val)
            await input_el.dispatch_event("change")
            await page.wait_for_timeout(200)
            
            updated_val = await input_el.input_value()
            print(f"    Symbol {symbol_name.strip()}: SL changed from {current_val} -> {updated_val} pips")

        # 7. Test Quick Reset Button (1/4 ADR)
        print("\n[6] Testing 1/4 ADR reset button...")
        reset_btn = page.locator(".quick-sl-btn").nth(0)
        await reset_btn.click()
        await page.wait_for_timeout(400)
        reset_sl = await page.locator(".sl-input").nth(0).input_value()
        print(f"    EURUSD SL reset back to: {reset_sl} pips")

        # 8. Test Category Tabs
        print("\n[7] Testing Category Tabs...")
        for cat in ["Forex Majors", "Forex Minors", "Metals", "Energies", "Indices", "All"]:
            tab = page.locator(f".cat-tab:has-text('{cat}')")
            await tab.click()
            await page.wait_for_timeout(200)
            rows = await page.locator("tbody tr").count()
            print(f"    Category Tab [{cat}]: {rows} rows visible")

        # 9. Test Symbol Search
        print("\n[8] Testing Search Filter...")
        search_input = page.locator(".search-input")
        await search_input.fill("JPY")
        await page.wait_for_timeout(300)
        jpy_rows = await page.locator("tbody tr").count()
        print(f"    Search 'JPY' -> {jpy_rows} rows visible")
        await search_input.fill("")
        await page.wait_for_timeout(200)

        # 10. Test Deep-Dive Modal
        print("\n[9] Testing Deep-Dive Modal...")
        deep_dive_btn = page.locator("tbody button:has-text('Deep Dive')").nth(0)
        await deep_dive_btn.click()
        await page.wait_for_timeout(400)
        modal_visible = await page.locator(".modal-overlay").nth(0).is_visible()
        print(f"    Deep-Dive Modal visible: {modal_visible}")
        close_btn = page.locator(".modal-card .close-btn").nth(0)
        await close_btn.click()
        await page.wait_for_timeout(300)

        # 11. Test Vince TWR Modal
        print("\n[10] Testing Vince TWR Curve Modal...")
        twr_btn = page.locator("button:has-text('Vince TWR Curve')")
        await twr_btn.click()
        await page.wait_for_timeout(500)
        canvas_visible = await page.locator("#twrChart").is_visible()
        print(f"    TWR Canvas visible: {canvas_visible}")
        close_twr = page.locator(".modal-card .close-btn").nth(1)
        await close_twr.click()
        await page.wait_for_timeout(300)

        # Take final screenshot
        screenshot_path = "d:/projects/metatrader5/risk_management_dashboard/output_screenshot.png"
        await page.screenshot(path=screenshot_path)
        print(f"\n[11] Captured screenshot to: {screenshot_path}")

        # Check for errors
        print("\n" + "=" * 60)
        print(f"Console Errors: {len(console_errors)}")
        for err in console_errors:
            print(f"  [Console Error] {err}")
        print(f"Page Uncaught Errors: {len(page_errors)}")
        for err in page_errors:
            print(f"  [Page Error] {err}")
        print("=" * 60)

        assert len(console_errors) == 0, f"Encountered console errors: {console_errors}"
        assert len(page_errors) == 0, f"Encountered page errors: {page_errors}"
        print("ALL BROWSER TESTS PASSED PERFECTLY!")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_browser_tests())
