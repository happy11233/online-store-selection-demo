import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

const apiBase = "http://127.0.0.1:8012/api";
const e2eUser = { username: "e2e_admin", password: "IsolatedDemoPass123!" };
let apiCsrf = "";

test.beforeEach(async ({ page, request }) => {
  const status = await (await request.get(apiBase + "/auth/status")).json();
  await page.goto("/workspace");
  await page.getByRole("textbox", { name: "用户名" }).fill(e2eUser.username);
  await page.getByLabel("密码", { exact: true }).fill(e2eUser.password);
  await page.getByRole("button", { name: status.data.initialized ? "登录" : "创建并进入" }).click();
  await expect(page.getByRole("heading", { name: "智能选品工作台" })).toBeVisible();
  const auth = await request.post(apiBase + "/auth/login", { data: e2eUser });
  expect(auth.ok()).toBe(true);
  apiCsrf = (await auth.json()).data.csrf_token;
});

test.describe("AIMid loop engineering demo", () => {
  test("observes a hotspot, recommends products, and drafts content", async ({ page }) => {
    await page.goto("/hotspots");
    await expect(page.locator(".content").getByRole("heading", { name: "热点趋势" })).toBeVisible();
    await expect(page.getByText("模拟时间序列")).toBeVisible();

    await page.locator("button").filter({ hasText: "使用该热点选品" }).nth(1).click();
    await expect(page).toHaveURL(/workspace\?hotspot_id=H2002/);
    await expect(page.getByRole("heading", { name: "智能选品工作台" })).toBeVisible();

    await page.getByRole("button", { name: "AI 一键选品" }).click();
    await expect(page.getByText("推荐商品榜单")).toBeVisible();
    await expect(page.getByText("低脂高蛋白鸡胸肉即食", { exact: true })).toBeVisible();
    await expect(page.getByText("清洗后候选")).toBeVisible();

    await page.getByRole("button", { name: "解释" }).click();
    await expect(page.getByText("AI 解释")).toBeVisible();
    await page.getByRole("button", { name: "关闭" }).click();

    await page.getByRole("button", { name: "内容" }).click();
    await expect(page.getByText("图文分镜")).toBeVisible();
    await expect(page.getByText("风险提示")).toBeVisible();
  });

  test("navigates to feedback without horizontal page overflow", async ({ page }) => {
    await page.goto("/feedback");
    await expect(page.locator(".content").getByRole("heading", { name: "投放回流" })).toBeVisible();
    await expect(page.getByText("新增回流样本")).toBeVisible();

    await page.getByRole("link", { name: "热点趋势" }).click();
    await expect(page).toHaveURL(/hotspots$/);
    await page.getByRole("link", { name: "选品工作台" }).click();
    await expect(page).toHaveURL(/workspace$/);
    const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(horizontalOverflow).toBe(false);
  });

  test("applies rule thresholds to a fresh recommendation", async ({ page, request }) => {
    test.skip(test.info().project.name !== "chromium", "Run mutable workflow once on desktop");
    const originalRules = (await (await request.get(apiBase + "/rules")).json()).data;

    try {
      await page.goto("/workspace?hotspot_id=H2002");
      await page.getByRole("button", { name: "AI 一键选品" }).click();
      await expect(page.getByText("低脂高蛋白鸡胸肉即食", { exact: true })).toBeVisible();

      await page.locator(".rules-card").getByRole("spinbutton").first().fill("100");
      const [saved] = await Promise.all([
        page.waitForResponse((response) => response.url() === apiBase + "/rules" && response.request().method() === "PUT"),
        page.getByRole("button", { name: "保存阈值" }).click(),
      ]);
      expect(saved.ok()).toBe(true);
      expect((await saved.json()).data.commission_min).toBe(1);

      await page.getByRole("button", { name: "AI 一键选品" }).click();
      await expect(page.getByText("暂无符合条件的商品")).toBeVisible();
      await expect(page.getByText("已过滤 7 件")).toBeVisible();
    } finally {
      const restored = await request.put(apiBase + "/rules", { data: originalRules, headers: { "X-CSRF-Token": apiCsrf } });
      expect(restored.ok()).toBe(true);
    }
  });

  test("downloads the current recommendation as CSV", async ({ page }) => {
    test.skip(test.info().project.name !== "chromium", "Check the download once on desktop");
    await page.goto("/workspace?hotspot_id=H2002");
    await page.getByRole("button", { name: "AI 一键选品" }).click();
    await expect(page.getByText("低脂高蛋白鸡胸肉即食", { exact: true })).toBeVisible();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: "导出 CSV" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("recommendations.csv");
    const chunks = [];
    for await (const chunk of await download.createReadStream()) chunks.push(chunk);
    const raw = Buffer.concat(chunks).toString("utf8");
    const csv = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;
    expect(csv).toContain("product_id,title,category,price");
    expect(csv).toContain("P1002,低脂高蛋白鸡胸肉即食");
  });

  test("submits feedback once, ignores duplicates, and creates a snapshot", async ({ page, request }) => {
    test.skip(test.info().project.name !== "chromium", "Run mutable workflow once on desktop");
    const initialCount = (await (await request.get(apiBase + "/feedback/records")).json()).meta.total;
    const initialSummary = (await (await request.get(apiBase + "/feedback/summary")).json()).data;
    const initialSnapshots = (await (await request.get(apiBase + "/loop/snapshots")).json()).data.length;

    await page.goto("/workspace?hotspot_id=H2002");
    await page.getByRole("button", { name: "AI 一键选品" }).click();
    const productRow = page.locator(".recommend-card tbody tr").filter({ hasText: "低脂高蛋白鸡胸肉即食" }).first();
    await productRow.getByRole("button", { name: "回流" }).click();
    await expect(page).toHaveURL(/feedback[?]product_id=P1002&hotspot_id=H2002&recommendation_id=rec-/);
    await expect(page.locator(".feedback-form select").first()).toHaveValue("P1002");
    await expect(page.locator(".feedback-form select").nth(1)).toHaveValue("H2002");

    const eventId = "e2e-" + randomUUID();
    await page.locator(".feedback-form input[placeholder]").fill(eventId);
    const inputs = page.locator(".feedback-form input[type=number]");
    for (const [index, value] of ["1234", "123", "12", "1", "480"].entries()) {
      await inputs.nth(index).fill(value);
    }
    const submit = page.getByRole("button", { name: "提交回流样本" });
    const [accepted] = await Promise.all([
      page.waitForResponse((response) => response.url() === apiBase + "/feedback" && response.request().method() === "POST"),
      submit.click(),
    ]);
    expect((await accepted.json()).data.received).toBe(true);
    expect(accepted.request().postDataJSON().recommendation_id).toMatch(/^rec-/);
    await expect(page.getByText("回流样本已写入，指标已刷新")).toBeVisible();
    await expect(page.locator(".feedback-table-card .section-heading .muted")).toHaveText("共 " + (initialCount + 1) + " 条");
    await expect(page.locator(".feedback-stats .stat").first().locator("strong")).toHaveText((initialSummary.impressions + 1234).toLocaleString());

    const [duplicate] = await Promise.all([
      page.waitForResponse((response) => response.url() === apiBase + "/feedback" && response.request().method() === "POST"),
      submit.click(),
    ]);
    expect((await duplicate.json()).data.duplicate).toBe(true);
    await expect(page.getByText("重复事件已忽略，指标未变")).toBeVisible();
    expect((await (await request.get(apiBase + "/feedback/records")).json()).meta.total).toBe(initialCount + 1);

    const [snapshotResponse] = await Promise.all([
      page.waitForResponse((response) => response.url() === apiBase + "/loop/snapshots" && response.request().method() === "POST"),
      page.getByRole("button", { name: "生成快照" }).click(),
    ]);
    const snapshot = (await snapshotResponse.json()).data;
    expect(snapshot.simulation).toBe(true);
    expect(snapshot.sample_count).toBe(initialCount + 1);
    await expect(page.getByText(snapshot.status === "ready" ? "Demo 训练快照已生成，评估指标为模拟值" : "Demo 训练快照已生成，仍需积累回流样本")).toBeVisible();
    await expect(page.getByText(snapshot.snapshot_id)).toBeVisible();
    await expect(page.locator(".snapshot-count")).toHaveText("已生成 " + (initialSnapshots + 1) + " 个训练快照");
  });

  test("connects both mock sources and shows the guarded official API entry", async ({ page, request }) => {
    test.skip(test.info().project.name !== "chromium", "Run source mutation once on desktop");
    await page.getByRole("link", { name: "数据源接入" }).click();
    await expect(page.locator(".content").getByRole("heading", { name: "数据源接入" })).toBeVisible();
    await expect(page.getByText("抖音官方 API 接入入口")).toBeVisible();
    const cards = page.locator(".source-card");
    for (const [index, resource] of ["products", "hotspots"].entries()) {
      const card = cards.nth(index);
      await card.getByRole("button", { name: "连接模拟数据" }).click();
      await card.getByRole("button", { name: "立即同步" }).click();
      await expect(card.getByText("同步成功")).toBeVisible();
      const payload = await (await request.get(apiBase + "/data-sources")).json();
      expect(payload.data.find((row) => row.resource === resource).snapshot_id).toMatch(/^mock-/);
    }
    await page.getByRole("button", { name: "检查正式授权入口" }).click();
    await expect(page.getByRole("status")).toContainText("本地 Demo 禁止真实授权");
    expect((await (await request.get(apiBase + "/integrations/douyin/status")).json()).data.outbound_requests).toBe(false);
  });

  test("signs out and guards direct navigation", async ({ page }) => {
    await page.reload();
    await expect(page.getByRole("heading", { name: "智能选品工作台" })).toBeVisible();
    await page.getByRole("button", { name: "退出登录" }).click();
    await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
    await page.goto("/feedback");
    await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
  });

  test("viewer sees read only controls and cannot open administration", async ({ page, request }) => {
    test.skip(test.info().project.name !== "chromium", "Create test account once on desktop");
    const body = { username: "e2e_viewer_" + randomUUID().slice(0, 8), password: "ViewerDemoPass123!", role: "viewer" };
    await page.getByRole("link", { name: "账号与权限" }).click();
    await expect(page.locator(".content").getByRole("heading", { name: "账号与权限" })).toBeVisible();
    await page.locator(".account-form").getByRole("textbox", { name: "用户名" }).fill(body.username);
    await page.locator(".account-form").getByLabel(/密码/).fill(body.password);
    await page.locator(".account-form select").selectOption("viewer");
    await page.getByRole("button", { name: "创建账号" }).click();
    await expect(page.getByRole("status")).toContainText("系统账号已创建");
    await page.getByRole("button", { name: "退出登录" }).click();
    await expect(page.getByRole("heading", { name: "登录工作台" })).toBeVisible();
    await page.getByRole("textbox", { name: "用户名" }).fill(body.username);
    await page.getByLabel("密码", { exact: true }).fill(body.password);
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await expect(page.getByRole("button", { name: "AI 一键选品" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "保存阈值" })).toBeDisabled();
    await expect(page.getByRole("link", { name: "账号与权限" })).toHaveCount(0);
    await page.goto("/users");
    await expect(page).toHaveURL(/workspace$/);
    const denied = await request.post(apiBase + "/auth/login", { data: body });
    expect(denied.ok()).toBe(true);
    const viewerCsrf = (await denied.json()).data.csrf_token;
    const forbidden = await request.put(apiBase + "/rules", { data: { commission_min: 0.2 }, headers: { "X-CSRF-Token": viewerCsrf } });
    expect(forbidden.status()).toBe(403);
  });
});

test("mobile workspace keeps the main action visible", async ({ page }) => {
  await page.goto("/workspace?hotspot_id=H2002");
  await expect(page.getByRole("button", { name: "AI 一键选品" })).toBeVisible();
  await expect(page.getByText("模型运行状态")).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("workspace-mobile.png"), fullPage: true });
});
