# -*- coding: utf-8 -*-
"""知妍 Agent 演示视频自动录制脚本（Playwright）。

按 docs/demo_video_script.md 的八幕分镜自动驱动真实页面并连续录像，
输出一个 WebM 文件，后期与口播对齐剪辑（片头用 zhiyan_intro_notext.mp4）。

使用前提：
  1. 已安装依赖：pip install playwright && playwright install chromium
  2. 知妍服务已启动：scripts/run_service.cmd（9000 端口）

运行方式：
  python scripts/record_demo.py              # 有头模式录制，可实时观看
  python scripts/record_demo.py --headless   # 无头模式后台录制

输出：
  output/video/demo_recording_<时间戳>.webm  （整段连续录像）
  output/video/step_fail_*.png               （某一步失败时的现场截图）
"""
import argparse
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page

BASE = "http://localhost:9000"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "video"
ATTACH_FILE = ROOT / "紫白可爱云朵精灵.png"   # 幕4 上传用的本地测试图片
QUESTION = "护发精油孕妇能用吗？"             # 幕4 自由提问（知识库可命中）

results: list[tuple[str, str]] = []          # (幕名, ok/skip/fail:原因)


def record(name: str, error: Exception | None = None) -> None:
    tag = "ok" if error is None else f"fail:{type(error).__name__}:{error}"
    results.append((name, tag))
    print(f"[{'OK ' if error is None else 'FAIL'}] {name} {'' if error is None else error}")


async def wait_analysis_done(page: Page, timeout_s: int = 150) -> bool:
    """等待幕3 Agent 分析完成：总结/行动/建议三条消息出齐（或超时）。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if await page.locator(".chat-inline-actions").count() and \
               await page.locator(".chat-insert-btn").count():
                return True
        except Exception:
            pass
        await page.wait_for_timeout(1000)
    return False


async def wait_reply_done(page: Page, before_count: int, timeout_s: int = 120) -> bool:
    """等待幕4 自由提问回答完成：消息行数增加且加载态消失。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            lines = await page.locator(".agent-chat-line").count()
            loading = await page.locator(".chat-loading").count()
            if lines > before_count and loading == 0:
                return True
        except Exception:
            pass
        await page.wait_for_timeout(1000)
    return False


async def scene1_overview(page: Page) -> None:
    """幕1 工作台总览：全景停留约 10 秒。"""
    await page.goto(f"{BASE}/workbench", wait_until="domcontentloaded")
    await page.wait_for_selector(".session-item", timeout=20000)
    await page.wait_for_selector(".agent-chat", timeout=20000)
    await page.wait_for_timeout(10000)
    record("幕1 工作台总览")


async def scene2_insight(page: Page) -> None:
    """幕2 客户洞察：选中 S00082（按昵称定位），停留看洞察卡与订单卡。"""
    data = await page.request.get(f"{BASE}/api/workbench/sessions")
    items = (await data.json()).get("items", [])
    nickname = next((it["buyer_nickname"] for it in items if it.get("conversation_id") == TARGET_SESSION), "")
    item = page.locator(".session-item", has_text=nickname).first if nickname \
        else page.locator(".session-item").first
    await item.click()
    await page.wait_for_timeout(3000)                      # 等会话与洞察加载
    await page.locator(".customer-insight-card").first.hover()
    await page.wait_for_timeout(3000)
    await page.mouse.wheel(0, 0)                           # 保持画面稳定
    await page.wait_for_timeout(3000)
    record("幕2 客户洞察", None if nickname else RuntimeError(f"列表未找到 {TARGET_SESSION}，已点击首项"))


async def scene3_analysis(page: Page) -> None:
    """幕3 Agent 自动分析：等待三条消息依次出现并停留展示。"""
    done = await wait_analysis_done(page)
    await page.wait_for_timeout(5000)                      # 总结气泡停留
    await page.locator(".chat-inline-actions").first.hover()
    await page.wait_for_timeout(3000)                      # 建议行动停留
    await page.locator(".chat-insert-btn").first.hover()
    await page.wait_for_timeout(3000)                      # 建议回复停留
    record("幕3 Agent 自动分析", None if done else RuntimeError("分析等待超时(150s)"))


async def scene4_interact(page: Page) -> None:
    """幕4 附件上传（产生客服气泡）、气泡操作、快捷行动、自由问答。"""
    # ① 附件上传：向隐藏 file input 注入本地图片（上传后出现客服侧行）
    await page.locator(".agent-chat-input input[type=file]").set_input_files(str(ATTACH_FILE))
    await page.wait_for_selector(".chat-attachment-img", timeout=20000)
    await page.wait_for_timeout(3000)
    # ② hover 展示气泡操作图标（客服侧与知妍侧各停 2 秒）
    await page.locator(".agent-chat-line.operator .agent-chat-bubble").first.hover()
    await page.wait_for_timeout(2000)
    await page.locator(".agent-chat-line.copilot .agent-chat-bubble").first.hover()
    await page.wait_for_timeout(2000)
    # ③ 点击第一个建议行动，等结果返回
    await page.locator(".chat-inline-actions .quick-action").first.click()
    await page.wait_for_timeout(6000)
    # ④ 自由提问（RAG），等回答完成
    before = await page.locator(".agent-chat-line").count()
    box = page.locator('input[placeholder="向知妍发送消息"]')
    await box.fill(QUESTION)
    await page.wait_for_timeout(800)
    await page.locator(".trae-send-btn").click()
    answered = await wait_reply_done(page, before)
    await page.wait_for_timeout(3000)
    record("幕4 交互与附件", None if answered else RuntimeError("自由提问等待超时(120s)"))


async def scene5_reply_loop(page: Page) -> None:
    """幕5 回复闭环：复制到回复框 → 编辑 → 发送 → 全屏进出。"""
    await page.locator(".chat-insert-btn").first.click()
    await page.wait_for_timeout(2000)
    editor = page.locator(".reply-editor textarea")
    await editor.click()
    await editor.fill("您好，已为您核实退货已入库，12 元线下退款申请已提交，财务审核到账后会在 24 小时内同步您，请留意支付宝消息，感谢理解。")
    await page.wait_for_timeout(2500)
    await page.locator(".reply-send").click()
    await page.wait_for_timeout(3000)
    # 全屏进出
    await page.locator(".fs-toggle").click()
    await page.wait_for_timeout(3000)
    await page.locator(".fs-toggle").click()
    await page.wait_for_timeout(2000)
    record("幕5 回复闭环")


async def scene6_dashboard(page: Page) -> None:
    """幕6 风险看板：指标卡 → 来源条形筛选 → 清除筛选。"""
    await page.goto(f"{BASE}/risk-dashboard", wait_until="domcontentloaded")
    await page.wait_for_selector(".risk-metrics", timeout=20000)
    await page.wait_for_timeout(5000)
    bars = page.locator(".chart-bar-row")
    if await bars.count():
        await bars.first.click()
        await page.wait_for_timeout(4000)                  # 筛选效果停留
        clear = page.get_by_role("button", name="清除筛选")
        if await clear.count():
            await clear.first.click()
            await page.wait_for_timeout(3000)
    record("幕6 风险看板")


async def scene7_detail(page: Page) -> None:
    """幕7 风险详情：打开弹窗 → 滚动各区块 → 改状态写备注 → 保存 → 关闭。"""
    detail_btn = page.locator(".risk-row button.secondary", has_text="查看详情").first
    await detail_btn.click()
    await page.wait_for_selector(".risk-detail-modal", timeout=10000)
    await page.wait_for_timeout(3000)
    await page.locator(".risk-detail-modal .detail-timeline").evaluate(
        "el => el.scrollTo({top: el.scrollHeight, behavior: 'smooth'})")
    await page.wait_for_timeout(3000)
    await page.locator(".risk-detail-modal select").select_option("processing")
    await page.locator(".risk-detail-modal textarea").fill("已电话安抚客户，工单加急跟进中，明日同步处理结果。")
    await page.wait_for_timeout(2500)
    await page.get_by_role("button", name="保存状态").click()
    await page.wait_for_timeout(4000)                      # 等保存完成
    await page.locator(".modal-close").click()
    await page.wait_for_timeout(2000)
    record("幕7 风险详情")


async def main(headless: bool) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        scenes = [scene1_overview, scene2_insight, scene3_analysis,
                  scene4_interact, scene5_reply_loop, scene6_dashboard, scene7_detail]
        for scene in scenes:
            try:
                await scene(page)
            except Exception as e:                     # 单幕失败不中断整段录制
                record(scene.__name__, e)
                await page.screenshot(path=str(OUT_DIR / f"step_fail_{scene.__name__}.png"))
        video = page.video
        await context.close()                          # 关闭后录像文件才落盘
        raw = await video.path()
        final = OUT_DIR / f"demo_recording_{stamp}.webm"
        raw.rename(final)
        await browser.close()
    print("\n===== 录制结果 =====")
    for name, tag in results:
        print(f"{name}: {tag}")
    print(f"\n录像文件：{final}")
    fails = [n for n, t in results if t != "ok"]
    print(f"共 {len(results)} 幕，成功 {len(results) - len(fails)}，失败 {len(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    import asyncio
    parser = argparse.ArgumentParser(description="知妍演示视频自动录制")
    parser.add_argument("--headless", action="store_true", help="无头模式（不显示浏览器窗口）")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.headless)))
