// Browser end-to-end, part 1: a person sets up the dashboard, adds a source, confirms the
// rights of the discovered video, and waits until the workers have dubbed and checked it.
//   node tools/ui_e2e_part1.mjs http://127.0.0.1:8800 /path/to/videos /path/to/screenshots
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");

const [base, videosDir, shots] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const step = (m) => console.log(new Date().toISOString().slice(11, 19), m);

await page.goto(base + "/");
await page.screenshot({ path: `${shots}/01_cai_dat_lan_dau.png` });
await page.fill('input[name="username"]', "admin");
await page.fill('input[name="password"]', "matkhau-quantri");
await page.fill('input[name="password2"]', "matkhau-quantri");
await page.click("button.primary");
await page.waitForURL(base + "/");
step("đã tạo tài khoản quản trị");

await page.goto(base + "/source/new");
await page.fill('input[name="name"]', "phim-blender-cc-by");
await page.selectOption("#stype", "folder");
await page.fill('input[name="path"]', videosDir);
await page.selectOption('select[name="license"]', "cc-by");
await page.fill('input[name="attribution"]', "(CC) Blender Foundation | mango.blender.org");
await page.fill('input[name="language"]', "en");
await page.fill('input[name="interval_minutes"]', "1");
await page.check('input[name="rights"][value="needs_approval"]');
await page.screenshot({ path: `${shots}/02_them_nguon.png`, fullPage: true });
await page.click('button:has-text("Lưu nguồn")');
await page.waitForURL(base + "/sources");
step("đã thêm nguồn");

// wait for the worker to find the video
let row;
for (let i = 0; i < 60; i++) {
  await page.goto(base + "/videos?state=AWAITING_RIGHTS");
  row = await page.$('a[href^="/video?id="]');
  if (row) break;
  await page.waitForTimeout(3000);
}
if (!row) throw new Error("không thấy video chờ xác minh quyền");
await page.goto(base + "/sources");
await page.screenshot({ path: `${shots}/03_nguon.png`, fullPage: true });
await page.goto(base + "/videos?state=AWAITING_RIGHTS");
await page.click('a[href^="/video?id="]');
await page.screenshot({ path: `${shots}/04_cho_xac_minh_quyen.png`, fullPage: true });
await page.fill('input[name="note"]', "Đã kiểm tra download.blender.org: Tears of Steel phát hành theo CC-BY 3.0, ghi công Blender Foundation");
await page.click('button:has-text("Xác nhận quyền và cho tải")');
const videoUrl = page.url();
step("đã xác nhận quyền: " + videoUrl);

// the workers download, dub and check; the page refreshes itself
let state = "";
let shotBusy = false;
for (let i = 0; i < 400; i++) {
  await page.goto(videoUrl);
  state = (await page.textContent(".badge")).trim();
  if (!shotBusy && state.startsWith("Đang lồng tiếng")) {
    await page.goto(base + "/");
    await page.screenshot({ path: `${shots}/05_tong_quan_dang_xu_ly.png`, fullPage: true });
    shotBusy = true;
    continue;
  }
  if (state.startsWith("Cần duyệt") || state.startsWith("Đạt kiểm tra") || state.startsWith("Lỗi")) break;
  await page.waitForTimeout(5000);
}
step("trạng thái: " + state);
await page.goto(videoUrl);
await page.screenshot({ path: `${shots}/06_video_sau_lan_dau.png`, fullPage: true });
await browser.close();
console.log("VIDEO_URL=" + videoUrl);
