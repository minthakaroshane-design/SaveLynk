
import React, { useState } from "react";
import {
  Download,
  Link2,
  ArrowRight,
  Clipboard,
  ShieldCheck,
  Zap,
  Layers,
  CheckCircle2,
  AlertCircle,
  Menu,
  Image as ImageIcon,
  Video,
  ChevronDown,
  Check,
  Sparkles,
  LoaderCircle
} from "lucide-react";

import {
  SiTiktok,
  SiInstagram,
  SiYoutube,
  SiFacebook,
  SiX,
  SiPinterest,
  SiReddit
} from "react-icons/si";

const platforms = [
  { name: "TikTok", domain: "tiktok.com", Icon: SiTiktok, slug: "tiktok" },
  { name: "Instagram", domain: "instagram.com", Icon: SiInstagram, slug: "instagram" },
  { name: "YouTube", domain: "youtube.com", Icon: SiYoutube, slug: "youtube" },
  { name: "Facebook", domain: "facebook.com", Icon: SiFacebook, slug: "facebook" },
  { name: "X / Twitter", domain: "x.com", Icon: SiX, slug: "twitter" },
  { name: "Pinterest", domain: "pinterest.com", Icon: SiPinterest, slug: "pinterest" },
  { name: "Reddit", domain: "reddit.com", Icon: SiReddit, slug: "reddit" }
];

function formatBytes(n) {
  if (!n) return "";
  let i = 0;
  while (n >= 1024 && i < 4) {
    n /= 1024;
    i++;
  }
  return n.toFixed(i ? 1 : 0) + " " + ["B", "KB", "MB", "GB", "TB"][i];
}

function QualitySelector({ qualities, value, onChange, disabled }) {
  const options = Array.isArray(qualities) ? qualities : [];
  const selected = options.find(q => q.value === value);

  return (
    <div className="quality-panel">
      <div className="quality-heading">
        <span>
          <Sparkles size={18} />
          Download quality
        </span>
        <span className="quality-current">
          {selected?.label || "Best available"}
        </span>
      </div>

      <div className="quality-options" role="group" aria-label="Download quality">
        {options.map(q => (
          <button
            type="button"
            key={q.value}
            disabled={disabled}
            className={`quality-option ${value === q.value ? "selected" : ""}`}
            onClick={() => onChange(q.value)}
            aria-pressed={value === q.value}
          >
            <span className="quality-indicator">
              {value === q.value && <Check size={12} strokeWidth={3} />}
            </span>
            {q.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [url, setUrl] = useState("");
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [quality, setQuality] = useState("best");
  const [status, setStatus] = useState("");
  const [menu, setMenu] = useState(false);

  const analyze = async () => {
    if (!url.trim()) return;

    setError("");
    setInfo(null);
    setBusy(true);
    setStatus("Analyzing media…");

    try {
      const r = await fetch("/api/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() })
      });

      const j = await r.json();

      if (!r.ok) {
        throw Error(j.detail || j.error || "Unable to analyze link");
      }

      setInfo(j);

      const available = Array.isArray(j.qualities) ? j.qualities : [];
      setQuality(
        available.some(q => q.value === "best")
          ? "best"
          : available[0]?.value || "best"
      );

      setStatus("");
    } catch (e) {
      setError(e.message || "Unable to analyze link");
      setStatus("");
    } finally {
      setBusy(false);
    }
  };

  const download = async (zip = false) => {
    if (busy) return;

    setBusy(true);
    setError("");
    setStatus("Preparing your download…");

    try {
      const r = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, quality, zip })
      });

      if (!r.ok) {
        let message = "Download failed";

        try {
          const j = await r.json();
          message = j.detail || j.error || message;
        } catch {
          // Keep the default error message.
        }

        throw Error(message);
      }

      const blob = await r.blob();
      const disposition = r.headers.get("Content-Disposition") || "";
      const match = disposition.match(
        /filename\*?=(?:UTF-8''|")?([^";]+)/i
      );

      const name = match
        ? decodeURIComponent(match[1].replace(/"/g, ""))
        : zip
          ? "savelynk-gallery.zip"
          : "savelynk-download";

      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = objectUrl;
      a.download = name;

      document.body.appendChild(a);
      a.click();
      a.remove();

      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
      setStatus("Download ready!");
    } catch (e) {
      setError(e.message || "Download failed");
      setStatus("");
    } finally {
      setBusy(false);
    }
  };

  const copyFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setUrl(text);
      setInfo(null);
      setError("");
      setStatus("");
    } catch {
      setError("Clipboard unavailable. Paste manually.");
    }
  };

  return (
    <div className="page">
      {/* Background atmosphere */}
      <div className="orb orb1" aria-hidden="true" />
      <div className="orb orb2" aria-hidden="true" />

      <div className="wave-layer wave-layer-one" aria-hidden="true" />
      <div className="wave-layer wave-layer-two" aria-hidden="true" />
      <div className="wave-layer wave-layer-three" aria-hidden="true" />

      {/* Navigation */}
      <header className="nav">
        <a className="logo" href="#home">
          <span className="logoicon">↧</span>
          Save<span>Lynk</span>
        </a>

        <nav className={menu ? "open" : ""}>
          <a href="#platforms" onClick={() => setMenu(false)}>
            Platforms
          </a>
          <a href="#how" onClick={() => setMenu(false)}>
            How it works
          </a>
          <a href="#faq" onClick={() => setMenu(false)}>
            FAQ
          </a>
        </nav>

        <button
          type="button"
          className="mobile-menu"
          onClick={() => setMenu(!menu)}
          aria-label="Toggle menu"
          aria-expanded={menu}
        >
          <Menu size={23} />
        </button>

        <a className="navpill" href="#downloader">
          Get Started <ArrowRight size={15} />
        </a>
      </header>

      <main id="home">
        {/* Hero */}
        <section className="hero">
          <div className="eyebrow">
            <span className="dot" />
            All your favorite platforms. One place.
          </div>

          <h1>
            Your media.
            <br />
            <em>Your way.</em>
          </h1>

          <p className="subtitle">
            Download supported videos, photos and galleries in the highest
            available quality. Simple, beautiful, and built for speed.
          </p>

          {/* Downloader */}
          <div id="downloader" className="downloader">
            <div className="downhead">
              <span>
                <Link2 size={17} />
                Paste a media link
              </span>

              <span className="secure">
                <ShieldCheck size={15} />
                Private by design
              </span>
            </div>

            <form
              className="inputrow"
              onSubmit={e => {
                e.preventDefault();
                analyze();
              }}
            >
              <input
                type="url"
                required
                value={url}
                onChange={e => {
                  setUrl(e.target.value);
                  setInfo(null);
                  setError("");
                  setStatus("");
                }}
                placeholder="Paste a TikTok, Instagram, YouTube link…"
                aria-label="Media URL"
              />

              <button
                type="button"
                className="paste"
                title="Paste from clipboard"
                onClick={copyFromClipboard}
              >
                <Clipboard size={18} />
              </button>

              <button
                className="primary"
                disabled={busy || !url.trim()}
                type="submit"
              >
                {busy ? (
                  <>
                    <LoaderCircle size={18} className="spin-icon" />
                    Working…
                  </>
                ) : (
                  <>
                    Analyze <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>

            <div className="helper">
              Supports public media you own or have permission to download.
            </div>

            {error && (
              <div className="notice error" role="alert">
                <AlertCircle size={17} />
                {error}
              </div>
            )}

            {status && (
              <div className="notice" role="status">
                {busy ? (
                  <LoaderCircle size={17} className="spin-icon" />
                ) : (
                  <CheckCircle2 size={17} />
                )}
                {status}
              </div>
            )}

            {info && (
              <div className="result">
                <div className="preview">
                  {info.thumbnail ? (
                    <img
                      src={info.thumbnail}
                      alt="Media thumbnail"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <div className="noimg">
                      <Video size={38} />
                    </div>
                  )}

                  <div>
                    <span className="small-label">
                      {info.platform} ·{" "}
                      {info.count > 1
                        ? `${info.count} items`
                        : "Media ready"}
                    </span>

                    <h3>{info.title || "Untitled media"}</h3>

                    <p>
                      {info.duration
                        ? `${Math.round(info.duration)} seconds · `
                        : ""}
                      {info.type === "image"
                        ? "Photo / gallery"
                        : "Video / media"}
                      {" · "}
                      {info.uploader || "Public post"}
                    </p>
                  </div>
                </div>

                <QualitySelector
                  qualities={info.qualities}
                  value={quality}
                  onChange={setQuality}
                  disabled={busy}
                />

                <div className="actions">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => download(false)}
                    className="primary"
                  >
                    <Download size={18} />
                    Download {info.count > 1 ? "items" : "media"}
                  </button>

                  {info.count > 1 && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => download(true)}
                      className="secondary"
                    >
                      <Layers size={18} />
                      Download ZIP
                    </button>
                  )}
                </div>

                <p className="result-note">
                  {info.note ? `${info.note} ` : ""}
                  Formats and resolutions depend on the source.
                  Large files may take longer to process.
                </p>
              </div>
            )}
          </div>

          <div className="trust">
            <span>
              <Zap size={17} /> Optimized processing
            </span>
            <span>
              <ImageIcon size={17} /> Photos + Videos
            </span>
            <span>
              <ShieldCheck size={17} /> No account needed
            </span>
          </div>
        </section>

        {/* Platforms */}
        <section id="platforms" className="section platforms">
          <div className="sectiontag">SUPPORTED PLATFORMS</div>

          <h2>One link. Endless possibilities.</h2>
          <p>Seven platforms, one beautifully simple experience.</p>

          <div className="platformgrid">
            {platforms.map(({ name, Icon, slug }) => (
              <div className={`platform ${slug}`} key={name}>
                <div className="platformsymbol">
                  <Icon size={31} />
                </div>

                <strong>{name}</strong>
                <span>Photos & videos*</span>
              </div>
            ))}
          </div>

          <p className="footnote">
            *Support depends on publicly available media and platform
            restrictions.
          </p>
        </section>

        {/* How it works */}
        <section id="how" className="section how">
          <div className="sectiontag">EFFORTLESS BY DESIGN</div>
          <h2>Three steps. That's it.</h2>

          <div className="steps">
            <article>
              <div className="stepicon">
                <Link2 />
              </div>
              <b>01 · Paste</b>
              <h3>Drop your link</h3>
              <p>
                Copy a supported public media URL and paste it above.
              </p>
            </article>

            <article>
              <div className="stepicon">
                <ChevronDown />
              </div>
              <b>02 · Choose</b>
              <h3>Pick your quality</h3>
              <p>
                Preview the content and select from available resolutions.
              </p>
            </article>

            <article>
              <div className="stepicon">
                <Download />
              </div>
              <b>03 · Save</b>
              <h3>Get your media</h3>
              <p>
                Download the file or package a gallery into a ZIP.
              </p>
            </article>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="section faq">
          <div className="sectiontag">GOOD TO KNOW</div>
          <h2>Frequently asked questions</h2>

          <details>
            <summary>Is SaveLynk free?</summary>
            <p>Yes. This local build has no payments or accounts.</p>
          </details>

          <details>
            <summary>Can I download private posts?</summary>
            <p>
              No. This version is intended for publicly accessible media
              that you have the right to save.
            </p>
          </details>

          <details>
            <summary>Why is a quality missing?</summary>
            <p>
              Available resolutions depend on the platform and media source.
              Some high-quality video requires audio/video merging.
            </p>
          </details>

          <details>
            <summary>Does it work on every post?</summary>
            <p>
              No downloader can guarantee that. Platforms may require
              authentication, change formats, block extraction, or
              restrict access.
            </p>
          </details>
        </section>
      </main>

      {/* Footer */}
      <footer>
        <div className="logo">
          ↧ Save<span>Lynk</span>
        </div>

        <p>
          Made for your media, your way. Respect creators and platform terms.
        </p>

        <span>© {new Date().getFullYear()} SaveLynk</span>
      </footer>
    </div>
  );
}
