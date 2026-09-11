# Option Edge AI product demo

- `option-edge-ai-demo.mp4`: 28 seconds, 1920 × 1080, 30 fps, H.264, silent, web fast-start.
- `option-edge-ai-poster.png`: dashboard poster for a README or portfolio.
- `storyboard.jpg`: six-frame overview.
- `render_demo.py`: editable, deterministic render source.

This is a designed interface walkthrough based on the repository's capabilities, not a recording of a running application. Prices, option quotes, headlines, and insights are illustrative sample data. Provider names and fallback adapters reflect the repository. The AI/LLM end-card label is the requested technology category; the current implementation uses factor-based explanations and FinBERT sentiment, not a demonstrated generative LLM call.

## Rebuild

On Windows with Segoe UI fonts installed:

```powershell
python -m pip install Pillow imageio-ffmpeg
python demo/render_demo.py
```

## GitHub presentation

Use the poster as a clickable video link in the root README:

```markdown
[![Option Edge AI product demo](demo/option-edge-ai-poster.png)](demo/option-edge-ai-demo.mp4)
```

For inline GitHub video playback, upload the MP4 through GitHub's attachment interface and place the resulting attachment URL on its own line in the README. The local file link above provides access to the repository file; it does not promise an inline player.

## Timeline

- 0–3s: title and subtitle.
- 3–6s: AAPL search and market dashboard.
- 6–10s: multi-provider aggregation and processing.
- 10–15s: calls, puts, expiration, strikes, IV, volume and open interest.
- 15–21s: market insights, watchlist signal, news and sentiment.
- 21–24s: completed research workspace and technical labels.
- 24–28s: closing title, technology stack and GitHub invitation.
