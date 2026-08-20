---
name: browser-firefox-mcp
description: "Firefox browser MCP server for penetration testing — XSS detection, session manipulation, network capture, recon."
---

# Firefox Browser MCP (cyberstrike)

Security-focused browser automation via MCP stdio. Uses Playwright + headless Firefox. Designed for integration with **cyberstrikeai** pentesting agent.

## Quick Deploy (Kali Linux)

```bash
cd ~/cyberstrike  # or your project root
git clone https://your-repo/browser-firefox-mcp.git
cd browser-firefox-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
playwright install --with-deps firefox
python server.py  # test: starts JSON-RPC on stdio
```

Or use the automated installer:

```bash
curl -fsSL https://your-repo/browser-firefox-mcp/raw/branch/main/setup.sh | bash
```

## Integration with cyberstrikeai

Add to your cyberstrikeai configuration (typically `~/.config/cyberstrikeai/config.json`):

```json
{
  "mcp_servers": {
    "firefox-browser": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/home/$USER/cyberstrike/browser-firefox-mcp"
    }
  }
}
```

The agent will auto-discover these tools:

### Navigation
| Tool | Description |
|---|---|
| `navigate(url)` | Go to URL |
| `go_back()` | Back in history |
| `go_forward()` | Forward in history |
| `reload_page()` | Reload current page |

### Interaction
| Tool | Description |
|---|---|
| `click(selector)` | Click element by CSS selector |
| `click_text(text)` | Click by visible text |
| `fill_input(selector, value)` | Fill form field |
| `press_key(key)` | Keyboard press (e.g. Enter, Tab) |
| `upload_file(selector, paths)` | File upload |

### Content Reading
| Tool | Description |
|---|---|
| `read_page()` | Full DOM + title + metadata |
| `get_text(selector)` | Extract visible text |
| `js_eval(expression)` | Run JavaScript |
| `screenshot(full_page, path)` | Screenshot (base64 or file) |
| `wait_for_selector(selector)` | Wait for element visibility |

### Security Testing 🔍
| Tool | Description |
|---|---|
| `inject_xss_payload(selector, payloads)` | Auto-probe XSS vectors into form fields |
| `inject_payload(selector, payload)` | Single custom payload injection |
| `find_reflection(text)` | Check if text was reflected in DOM |
| `get_url_params()` | List URL query parameters |

### Session Management 🎭
| Tool | Description |
|---|---|
| `get_cookies(domains?)` | Export all cookies |
| `set_cookie(name, value, domain)` | Inject single cookie |
| `set_cookies(list)` | Bulk-inject (Burp export compatible) |
| `delete_cookie(name)` | Remove a cookie |
| `clear_cookies()` | Clear all cookies |
| `get_session_info()` | Full snapshot: cookies + storage + tokens |
| `get_storage_data()` | localStorage + sessionStorage dump |
| `set_storage_item(k, v, store)` | Write to storage |
| `export_state(path)` | Save full context state |
| `import_state(path)` | Restore saved state |

### Network Capture 🌐
| Tool | Description |
|---|---|
| `start_network_capture()` | Begin capturing traffic |
| `stop_network_capture()` | Stop and report totals |
| `get_network_summary()` | Filtered traffic summary |
| `block_urls(patterns)` | Block URL patterns |

### Reconnaissance 🔎
| Tool | Description |
|---|---|
| `recon_technology_stack()` | Detect frameworks, CMS, analytics |
| `find_sensitive_data()` | Scan for leaked keys, tokens, secrets |
| `dom_analysis()` | DOM tree structural summary |
| `enumerate_forms()` | All forms with actions & field details |
| `enumerate_links(relative_only)` | Hyperlink inventory |
| `security_headers_check()` | CSP, X-Frame-Options, HSTS check |

## Architecture

```
cyberstrikeai agent
       │
       │  MCP JSON-RPC (stdio)
       ▼
  server.py          ← 同步 MCP stdio 服务（无 asyncio/trio 依赖）
       │
       ├── core/engine.py     → Playwright Firefox launcher
       ├── core/page.py       → Navigate / click / fill / screenshot
       ├── core/security.py   → XSS probing / reflection checks
       ├── core/session.py    → Cookie / storage / token ops
       ├── core/network.py    → Request/response capture
       └── core/recon.py      → Tech stack / sensitive data / DOM
```

## Notes

- **Headless by default** — no display needed; set `headless=false` in engine config for headed mode
- **Each tool is independent** — the server maintains stateful browser context across calls
- **Use `close_browser()` to release resources**, then next tool call auto-launches fresh instance
- **Windows note**: This skill targets Kali Linux. For Windows setup see `setup.ps1` companion
- **Firefox CDP limitations**: Some Chrome-specific CDP features unavailable; this uses Playwright's abstraction layer which works cross-browser
