# SaveLynk Complete — local development build

A premium React/Vite frontend and FastAPI/yt-dlp downloader backend for **public media that you own or are authorized to save**. Platforms: TikTok, Instagram, YouTube, Facebook, X, Pinterest, Reddit.

## Requirements
- Node.js 20+
- Python 3.10+
- FFmpeg installed and on PATH (`ffmpeg -version`)
- yt-dlp updated frequently (`python -m pip install -U yt-dlp`)

## Start (Windows PowerShell)
In terminal 1:
```powershell
cd server
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8787
```
In terminal 2, from the project root:
```powershell
npm install
npm run dev
```
Open **http://127.0.0.1:5173**.

## Important limitations
- This is a **local beta**, not a production-ready hosted service. Do not expose the backend to the internet as-is. Add authenticated job queues, bandwidth/storage quotas, domain/redirect SSRF controls, rate limiting, malware scanning, observability, reverse proxy protections, and per-request timeouts before public deployment.
- `yt-dlp` extraction is platform-dependent. Login-only, private, DRM-protected and inaccessible posts may fail. Some galleries/photo slideshows and original images may need platform-specific handlers. YouTube thumbnails and still images are not implemented as separate download options. Quality choices depend on extractor metadata.
- A gallery is automatically ZIP-packaged when multiple files are extracted; a separate ZIP button is also provided when metadata reports multiple items. This version does **not** support per-item gallery selection, guaranteed all-photo extraction, or a real-time progress bar.
- Backend temporarily saves downloads to disk and removes them after the HTTP response finishes. The browser may not display native progress until the server has finished processing.
- Downloads have a 750 MB per-file cap, a 30-item cap, and a 240-second subprocess timeout. ZIP downloads can still be large.
- Public media does not automatically imply permission to redistribute it. Respect copyright, creator permissions and platform terms.
- If `yt-dlp` isn't recognized, install it in the activated Python environment; check `yt-dlp --version`.

## Next engineering milestones
1. Platform-specific photo/gallery extraction adapters and regression tests with authorized sample URLs.
2. Streaming download jobs with real progress, cancellation, and transfer optimization.
3. Public-hosting security, queues, resource limits and policy/legal review.
4. SEO, accessibility audit and ad placement only after download reliability is validated.

## October 24 photo-support beta update

- Backend now attempts image-specific extraction and a public OpenGraph image fallback for Pinterest, Reddit, X, Instagram and Facebook when video extraction fails.
- Reddit public gallery JSON extraction is attempted for gallery posts.
- Image fallback **may provide only preview quality**; do not claim original resolution or complete albums.
- The frontend displays API error details instead of a generic error.
- Install the updated Python requirements again: `cd server`, activate `.venv`, then `pip install -r requirements.txt`.
- Restart the Uvicorn server after updating.
- No end-to-end live platform download tests were run in this environment. Some links will still fail due to authentication, changing APIs, hotlink protection, inaccessible images or platform restrictions.
- This is a **local development beta**, not production-safe hosting software. Before deployment add robust outbound request isolation, DNS rebinding protections, resource quotas, authentication/rate limiting and abuse controls.
