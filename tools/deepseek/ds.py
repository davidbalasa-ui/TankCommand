"""Call DeepSeek V4.1 Flash. Auth is injected by the sandbox proxy; no key is read here.

  ds.py new  PROMPT_FILE OUT_FILE
  ds.py cont CONVO_JSON PROMPT_FILE OUT_FILE [IMAGE.png ...]

Writes OUT_FILE (answer), OUT_FILE.reasoning, OUT_FILE.convo.json (whole conversation)
and prints one status line with token usage.
"""
import base64, json, sys, time, urllib.request

SYSTEM = ("You are a senior TypeScript engineer. You cannot run code, so you must be meticulous: "
          "mentally type-check and run every test you write. Follow the spec exactly and the output format strictly.")

def main():
    mode = sys.argv[1]
    if mode == 'new':
        prompt, out = sys.argv[2], sys.argv[3]
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": open(prompt).read()}]
    else:
        convo, prompt, out, imgs = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
        text = open(prompt).read()
        content = text if not imgs else [{"type": "text", "text": text}] + [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(open(p, 'rb').read()).decode()}}
            for p in imgs]
        msgs = json.load(open(convo)) + [{"role": "user", "content": content}]
    body = {"model": "deepseek-flash", "messages": msgs, "max_tokens": 300000, "stream": True,
            "stream_options": {"include_usage": True}}
    for attempt in range(4):
        try:
            t = time.time(); txt = []; rsn = []; usage = None; finish = None
            req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=json.dumps(body).encode(),
                                         headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=3600) as r:
                for line in r:
                    line = line.decode().strip()
                    if not line.startswith("data:"):
                        continue
                    d = line[5:].strip()
                    if d == "[DONE]":
                        break
                    j = json.loads(d)
                    if j.get("usage"):
                        usage = j["usage"]
                    for c in j.get("choices", []):
                        dl = c.get("delta", {})
                        if dl.get("content"): txt.append(dl["content"])
                        if dl.get("reasoning_content"): rsn.append(dl["reasoning_content"])
                        if c.get("finish_reason"): finish = c["finish_reason"]
            if not "".join(txt).strip():
                raise RuntimeError("empty answer (stream cut off)")
            break
        except Exception as e:  # network hiccup: back off and retry
            print("retry", attempt + 1, type(e).__name__, file=sys.stderr)
            time.sleep(2 ** (attempt + 1))
    else:
        print("FAILED: DeepSeek call did not complete"); sys.exit(2)
    content = "".join(txt)
    open(out, "w").write(content)
    open(out + ".reasoning", "w").write("".join(rsn))
    # Images are not kept in the stored conversation, to keep later rounds small.
    stored = msgs[:-1] + [{"role": "user", "content": msgs[-1]["content"] if isinstance(msgs[-1]["content"], str) else msgs[-1]["content"][0]["text"] + "\n[screenshots were attached here]"}]
    json.dump(stored + [{"role": "assistant", "content": content}], open(out + ".convo.json", "w"))
    u = usage or {}
    print(f"secs={round(time.time()-t)} finish={finish} in={u.get('prompt_tokens')} cached={u.get('prompt_cache_hit_tokens')} out={u.get('completion_tokens')}")

main()
