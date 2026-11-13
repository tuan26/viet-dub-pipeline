// Browser end-to-end, part 2: a reviewer fixes speakers, translations and voices on the
// review page, listens to a preview, saves and re-exports, then approves and downloads.
//   node tools/ui_e2e_part2.mjs BASE VIDEO_URL plan.json SHOTS_DIR OUT.mp4
// plan.json: {"speakers": {"12": "THOM"}, "translations": {"3": "..."}, "voices": {"THOM": "Nam — NamMinh (gốc)"}, "preview": 3}
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
import { readFileSync } from "node:fs";

const [base, videoUrl, planFile, shots, outFile] = process.argv.slice(2);
const plan = JSON.parse(readFileSync(planFile, "utf8"));
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
const page = await ctx.newPage();
const step = (m) => console.log(new Date().toISOString().slice(11, 19), m);
page.on("pageerror", (e) => console.log("PAGE ERROR", e.message));

await page.goto(base + "/login");
await page.fill('input[name="username"]', "admin");
await page.fill('input[name="password"]', "matkhau-quantri");
await page.click("button.primary");
await page.waitForURL(base + "/");

const id = new URL(videoUrl).searchParams.get("id");
await page.goto(`${base}/review?id=${encodeURIComponent(id)}`);
await page.screenshot({ path: `${shots}/07_trang_duyet.png`, fullPage: true });
await page.screenshot({ path: `${shots}/07b_trang_duyet_dau_trang.png` });

// speakers: a new name opens a prompt; answer it with the name
let pendingName = null;
page.on("dialog", (d) => d.accept(pendingName || ""));
for (const [index, name] of Object.entries(plan.speakers || {})) {
  const sel = page.locator(`#lines tr[data-index="${index}"] select.speaker`);
  const has = await sel.locator("option", { hasText: name }).count();
  if (has) await sel.selectOption({ label: name });
  else { pendingName = name; await sel.selectOption("__new__"); pendingName = null; }
}
for (const [index, text] of Object.entries(plan.translations || {})) {
  await page.fill(`#lines tr[data-index="${index}"] textarea.tr`, text);
}
for (const index of plan.skip || []) await page.check(`#lines tr[data-index="${index}"] input.skip`);
for (const [name, label] of Object.entries(plan.voices || {})) {
  await page.locator(`#cast tr[data-speaker="${name}"] select.voice`).selectOption({ label });
}
if (plan.confirm_speakers) await page.check("#confirm-speakers");
step("đã sửa: " + (await page.textContent("#dirty")));

// listen to one edited line before saving
if (plan.preview) {
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/review/preview")),
    page.click(`#lines tr[data-index="${plan.preview}"] .p-test`),
  ]);
  const body = await resp.json();
  const audio = await page.request.get(base + body.url);
  step(`nghe thử: ${resp.status()} → ${audio.status()} ${audio.headers()["content-type"]} ${(await audio.body()).length} byte`);
}
await page.locator(`#lines tr[data-index="${plan.preview || Object.keys(plan.translations)[0]}"]`).scrollIntoViewIfNeeded();
await page.screenshot({ path: `${shots}/08_dang_sua.png` });

await Promise.all([page.waitForURL(/\/video\?id=/, { timeout: 60000 }), page.click("#save-render")]);
step("đã lưu và gửi xuất lại");
let state = "";
const t0 = Date.now();
for (let i = 0; i < 200; i++) {
  await page.goto(`${base}/video?id=${encodeURIComponent(id)}`);
  state = (await page.textContent(".badge")).trim();
  if (state.startsWith("Cần duyệt") || state.startsWith("Đạt kiểm tra") || state.startsWith("Lỗi")) break;
  await page.waitForTimeout(3000);
}
step(`xuất lại xong sau ${Math.round((Date.now() - t0) / 1000)}s: ${state}`);
await page.screenshot({ path: `${shots}/09_sau_khi_xuat_lai.png`, fullPage: true });

await page.goto(`${base}/review?id=${encodeURIComponent(id)}`);
await page.screenshot({ path: `${shots}/10_trang_duyet_sau_sua.png`, fullPage: true });

await page.goto(`${base}/video?id=${encodeURIComponent(id)}`);
await page.fill('#decide input[name="note"]', plan.note || "Đã nghe lại toàn bộ, vai và bản dịch ổn");
if (await page.locator('input[name="override"]').count()) await page.check('input[name="override"]');
await page.click('button:has-text("Duyệt bản cuối")');
state = (await page.textContent(".badge")).trim();
step("sau khi duyệt: " + state);
await page.screenshot({ path: `${shots}/11_da_duyet.png`, fullPage: true });
const [download] = await Promise.all([page.waitForEvent("download"), page.click('a:has-text("Tải MP4")')]);
await download.saveAs(outFile);
step("đã tải MP4: " + outFile);

for (const [path, name] of [["/", "12_tong_quan"], ["/videos", "13_danh_sach_video"], ["/history", "14_lich_su"], ["/users", "15_tai_khoan"], ["/publish", "16_phat_hanh"]]) {
  await page.goto(base + path);
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
await browser.close();
