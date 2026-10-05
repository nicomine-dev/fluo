// Redirige a la ultima version publicada en GitHub Releases.
//   /descargar -> Fluo-Setup-x.y.z.exe      /portable -> Fluo-x.y.z-portable.zip
// Asi los links de la pagina y de los mensajes no cambian con cada version.
const REPO = "nicomine-dev/fluo";
const PATTERNS = {
  setup: /^Fluo-Setup-.*\.exe$/i,
  portable: /^Fluo-.*-portable\.zip$/i,
};

module.exports = async (req, res) => {
  const kind = String(req.query.a || "setup");
  const pattern = PATTERNS[kind] || PATTERNS.setup;
  const fallback = `https://github.com/${REPO}/releases/latest`;
  try {
    const r = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
      headers: { "User-Agent": "fluo-site", Accept: "application/vnd.github+json" },
    });
    if (!r.ok) throw new Error(`GitHub ${r.status}`);
    const release = await r.json();
    const asset = (release.assets || []).find((a) => pattern.test(a.name));
    res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate=86400");
    res.redirect(302, asset ? asset.browser_download_url : fallback);
  } catch (err) {
    res.setHeader("Cache-Control", "no-store");
    res.redirect(302, fallback);
  }
};
