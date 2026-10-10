from datetime import UTC, datetime

from app.ollama_quota import build_ollama_cookie_header, parse_ollama_quota_html


def test_build_ollama_cookie_header_raw_value():
    assert build_ollama_cookie_header("abc123") == "__Secure-session=abc123"


def test_build_ollama_cookie_header_full_cookie():
    cookie = "aid=x; __Secure-session=token123"
    assert build_ollama_cookie_header(cookie) == cookie


def test_parse_ollama_quota_html_legacy_span_heading():
    html = """
    <span>Cloud usage</span>
    <span class="text-xs font-normal px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-600 capitalize">pro</span>
    <div class="flex justify-between mb-2">
      <span class="text-sm text-neutral-400">Session usage</span>
      <span class="text-sm text-neutral-500">Weekly limit reached</span>
    </div>
    <div data-usage-track aria-label="Session usage 12.5% used"></div>
    <div class="local-time" data-time="2026-06-29T00:00:00Z">Sessions resume in 3 days.</div>
    <div class="flex justify-between mb-2">
      <span class="text-sm">Weekly usage</span>
      <span class="text-sm text-red-500">80% used</span>
    </div>
    <div data-usage-track aria-label="Weekly usage 80% used">
      <button data-usage-segment data-model="glm-5.2" data-requests="100" style="width: 80%; background: #3b82f6"></button>
    </div>
    <div class="local-time" data-time="2026-06-30T00:00:00Z">Resets in 4 days.</div>
    <script>
    """
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)
    plan, windows = parse_ollama_quota_html(html, now)
    assert plan == "pro"
    assert len(windows) == 2
    assert windows[0].label == "Session"
    assert windows[0].used == 12.5
    assert windows[0].status_text == "Weekly limit reached"
    assert windows[1].used == 80.0
    assert windows[1].models and windows[1].models[0].model == "glm-5.2"


def test_parse_ollama_quota_html_current_settings_page():
    html = """
    <h2 class="flex items-center gap-2 text-xl font-medium">Usage credits
      <span class="text-xs font-normal px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-600 capitalize">max</span>
    </h2>
    <h2 class="text-xl font-medium pt-4">Cloud usage</h2>
    <div class="flex justify-between mb-2">
      <span class="text-sm ">Session usage</span>
      <span class="text-sm ">0% used</span>
    </div>
    <div class="relative group" data-usage-meter>
      <div data-usage-bubble></div>
      <div class="relative h-3" data-usage-track aria-label="Session usage 0% used">
        <div class="flex h-full">
          <button data-usage-segment data-model="gpt-oss:20b" data-requests="2" style="width: 100%;"></button>
        </div>
      </div>
    </div>
    <div class="local-time" data-time="2026-10-10T06:00:00Z">Resets in 2 hours.</div>
    <div class="flex justify-between mb-2">
      <span class="text-sm">Weekly usage</span>
      <span class="text-sm">38.9% used</span>
    </div>
    <div data-usage-meter>
      <div data-usage-bubble></div>
      <div data-usage-track aria-label="Weekly usage 38.9% used">
        <div class="flex">
          <button data-usage-segment data-model="glm-5.3" data-requests="1668" style="width: 100%;"></button>
        </div>
      </div>
    </div>
    <div class="local-time" data-time="2026-10-12T00:00:00Z">Resets in 1 day.</div>
    <form method="POST" action="/settings">
      <input type="checkbox" name="notify-usage-limits" checked />
    </form>
    <script>
    function applyLocalTimeTitles() {}
    """
    now = datetime(2026, 10, 10, 4, 0, 0, tzinfo=UTC)
    plan, windows = parse_ollama_quota_html(html, now)
    assert plan == "max"
    assert len(windows) == 2
    assert windows[0].used == 0.0
    assert windows[0].status_text == "0% used"
    assert windows[1].used == 38.9
    assert windows[1].models and windows[1].models[0].model == "glm-5.3"
    assert windows[1].models[0].requests == 1668
