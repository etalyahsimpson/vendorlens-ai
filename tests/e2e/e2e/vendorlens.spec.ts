import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// Screenshots are committed at the repository root (assets/screenshots).
const SHOTS = process.env.SCREENSHOT_DIR
  ? process.env.SCREENSHOT_DIR
  : path.resolve(HERE, "..", "..", "..", "assets", "screenshots");

/**
 * End-to-end smoke flow against the running application:
 * overview -> sample data -> suggestions -> review decision (persisted)
 * -> export -> invalid upload handling -> genuine screenshots.
 */

test.describe("VendorLens AI end-to-end workflow", () => {
  test("overview renders the product story", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Find duplicate supplier records",
    );
    await expect(
      page.getByRole("button", { name: "Explore Sample Data" }).first(),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Upload Supplier CSV" }).first()).toBeVisible();
    await expect(page.getByRole("contentinfo")).toContainText(
      "Independent Engineering Portfolio Project",
    );
    await expect(page.getByRole("link", { name: /Official Portfolio/ })).toHaveAttribute(
      "href",
      "https://etalyahsimpson.github.io/",
    );
  });

  test("sample analysis surfaces ranked suggestions with evidence", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Explore Sample Data" }).first().click();
    await expect(page.getByRole("heading", { name: "Review Matches" })).toBeVisible();

    // Summary reflects real computed counts (header meta line + stat cards).
    await expect(page.getByText(/candidate pairs/).first()).toBeVisible();
    await expect(page.getByText("Likely matches")).toBeVisible();
    await expect(page.getByText("Needs review", { exact: true }).first()).toBeVisible();

    // Ranked suggestion table with scores and bands appears.
    const table = page.locator("table").first();
    await expect(table.getByText(/Likely match/).first()).toBeVisible({ timeout: 30_000 });
    await expect(table.getByText(/%/, { exact: false }).first()).toBeVisible();

    // Filters work: selecting "Likely match" keeps only likely rows.
    await page.locator("#band-filter").selectOption("likely_match");
    await expect(table.getByText(/Needs review/)).toHaveCount(0);
    await page.locator("#band-filter").selectOption("");
  });

  test("comparison drawer shows side-by-side evidence", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Explore Sample Data" }).first().click();
    await expect(page.getByRole("heading", { name: "Review Matches" })).toBeVisible();
    await expect(page.locator("table").first().getByRole("row").nth(1)).toBeVisible({
      timeout: 30_000,
    });

    await page.getByRole("button", { name: "Compare", exact: true }).first().click();
    const drawer = page.getByRole("heading", { name: "Review decision" });
    await expect(drawer).toBeVisible();
    await expect(page.getByText("Record A")).toBeVisible();
    await expect(page.getByText("Record B")).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirm same entity" })).toBeVisible();
  });

  test("review decision persists across a full page reload", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Explore Sample Data" }).first().click();
    await expect(page.getByRole("heading", { name: "Review Matches" })).toBeVisible();
    await expect(page.locator("table").first().getByRole("row").nth(1)).toBeVisible({
      timeout: 30_000,
    });

    await page.getByRole("button", { name: "Compare", exact: true }).first().click();
    await page.getByRole("button", { name: "Confirm same entity" }).click();
    await expect(page.getByText("Decision saved.")).toBeVisible();

    await page.reload();
    // The SPA restores the saved analysis; navigate back into the workspace.
    await expect(page.getByRole("button", { name: /Review Matches/ }).first()).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole("button", { name: /Review Matches/ }).first().click();
    await expect(page.getByRole("heading", { name: "Review Matches" })).toBeVisible();
    // The decision is restored from the backend after reload.
    await expect(page.getByText("Confirmed same entity").first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("export downloads a findings CSV including decisions", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Explore Sample Data" }).first().click();
    await expect(page.getByRole("heading", { name: "Review Matches" })).toBeVisible();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: "Export Findings" }).click(),
    ]);
    const name = download.suggestedFilename();
    expect(name).toContain("vendorlens_findings_");
    expect(name.endsWith(".csv")).toBeTruthy();
  });

  test("invalid upload shows a validation error", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Upload Supplier CSV" }).first().click();
    await expect(page.getByRole("heading", { name: "Upload Supplier CSV" })).toBeVisible();

    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Upload CSV file" }).click();
    const fc = await chooser;

    const badCsv = Buffer.from(
      "supplier_name,city\nOnly Name Field,Philadelphia\n",
      "utf-8",
    );
    await fc.setFiles({
      name: "bad.csv",
      mimeType: "text/csv",
      buffer: badCsv,
    });

    await expect(
      page.getByText(/Required columns are missing/i),
    ).toBeVisible();
  });

  test("valid upload flows into the review workspace", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Upload Supplier CSV" }).first().click();

    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Upload CSV file" }).click();
    const fc = await chooser;

    const goodCsv = Buffer.from(
      [
        "supplier_id,supplier_name,city,state,website",
        "SUP-001,Northstar Industrial Supplies LLC,Philadelphia,PA,northstarindustrial.example",
        "SUP-002,North Star Industrial Supply,Philadelphia,PA,northstarindustrial.example",
        "SUP-003,Northstar Office Services LLC,Philadelphia,PA,northstaroffice.example",
        "SUP-004,Silverline Packaging Corp.,Chicago,IL,silverlinepackaging.example",
      ].join("\n"),
      "utf-8",
    );
    await fc.setFiles({ name: "suppliers.csv", mimeType: "text/csv", buffer: goodCsv });

    await expect(page.getByRole("heading", { name: "Review Matches" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("4 records")).toBeVisible();
    await expect(page.getByText(/Northstar Industrial Supplies LLC/).first()).toBeVisible();
  });

  test("model performance page shows measured benchmark results", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Model Performance" }).first().click();
    await expect(page.getByRole("heading", { name: "Model Performance" })).toBeVisible();
    await expect(page.getByText("Precision", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Baseline vs trained model", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Confusion matrix")).toBeVisible();
    await expect(
      page.getByRole("link", { name: /read the methodology/i }),
    ).toHaveAttribute(
      "href",
      "https://github.com/etalyahsimpson/vendorlens-ai/blob/main/docs/ML_METHODOLOGY.md",
    );
  });
});

test.describe("Authentic application screenshots", () => {
  test("capture screenshots from the running application", async ({ page }) => {
    const shots = SHOTS;

    // 1. Overview (desktop).
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${shots}/overview.png`, fullPage: true });

    // 2. Review workspace with an active sample analysis.
    await page.getByRole("button", { name: "Explore Sample Data" }).first().click();
    await expect(page.getByRole("heading", { name: "Review Matches" })).toBeVisible();
    await expect(page.locator("table").first().getByRole("row").nth(1)).toBeVisible({
      timeout: 30_000,
    });
    // Let the transient "Sample analyzed" toast dismiss before capturing.
    await page.getByText("Sample analyzed:").waitFor({ state: "hidden", timeout: 10_000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${shots}/review-matches.png`, fullPage: false });

    // 3. Comparison drawer open with evidence + decision controls.
    await page.getByRole("button", { name: "Compare", exact: true }).first().click();
    await expect(page.getByRole("heading", { name: "Review decision" })).toBeVisible();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${shots}/comparison-review.png`, fullPage: true });

    // 4. Model performance page.
    await page.getByRole("button", { name: "Model Performance" }).first().click();
    await expect(page.getByText("Baseline vs trained model", { exact: true }).first()).toBeVisible();
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${shots}/model-performance.png`, fullPage: false });

    // 5. Mobile overview (390px).
    await page.getByRole("button", { name: "Overview" }).first().click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${shots}/overview-mobile.png`, fullPage: false });
  });
});
