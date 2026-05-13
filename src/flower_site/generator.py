from __future__ import annotations

import hashlib
import html
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageOps

from flower_id.manifest import load_rows
from flower_site.config import BuildConfig


THUMBNAIL_SIZE = (720, 540)
LARGE_SIZE = (1800, 1800)


@dataclass(frozen=True)
class FlowerContent:
    common_name: str
    cover_photo: str
    facts: tuple[str, ...]


@dataclass(frozen=True)
class SiteContent:
    title: str | None
    description: str | None
    flowers: dict[str, FlowerContent]


@dataclass(frozen=True)
class Photo:
    filename: str
    genus: str
    relative_path: Path
    source_path: Path
    thumb_url: str
    large_url: str


@dataclass(frozen=True)
class Flower:
    genus: str
    common_name: str
    cover: Photo
    photos: tuple[Photo, ...]
    facts: tuple[str, ...]
    page_url: str


def build_site(config: BuildConfig) -> None:
    rows = load_rows(config.app.paths.manifest_csv)
    sync_site_content(config.site.content_toml, rows, config.site.title, config.site.description)
    content = load_site_content(config.site.content_toml)
    output_dir = config.site.output_dir

    _ensure_safe_output_dir(output_dir)
    flowers = _build_flowers(rows, config.app.paths.bucket_root, output_dir, content)
    title = content.title or config.site.title
    description = content.description if content.description is not None else config.site.description

    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "assets").mkdir(parents=True, exist_ok=True)
    (output_dir / "flowers").mkdir(parents=True, exist_ok=True)
    (output_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)

    _write_text(output_dir / ".nojekyll", "")
    _write_text(output_dir / "assets" / "site.css", _render_css())

    for flower in flowers:
        for photo in flower.photos:
            _write_resized_image(photo.source_path, output_dir / photo.thumb_url, THUMBNAIL_SIZE)
            _write_resized_image(photo.source_path, output_dir / photo.large_url, LARGE_SIZE)
        _write_text(output_dir / flower.page_url, _render_flower_page(flower, title))

    _write_text(output_dir / "index.html", _render_index(flowers, title, description))
    print(f"Generated {len(flowers)} flower pages in {output_dir}.")


def load_site_content(path: Path) -> SiteContent:
    if not path.exists():
        return SiteContent(title=None, description=None, flowers={})

    with path.open("rb") as content_file:
        raw = tomllib.load(content_file)

    site = raw.get("site", {})
    flowers = {}
    for genus, values in raw.get("flowers", {}).items():
        if not isinstance(values, dict):
            raise SystemExit(f"Invalid site content for flowers.{genus}: expected a table.")
        facts = values.get("facts", [])
        if not isinstance(facts, list):
            raise SystemExit(f"Invalid facts for flowers.{genus}: expected a list of strings.")
        common_name = str(values.get("common_name", "")).strip()
        cover_photo = str(values.get("cover_photo", "")).strip()
        flowers[str(genus)] = FlowerContent(
            common_name=common_name or str(genus),
            cover_photo=cover_photo,
            facts=tuple(str(fact).strip() for fact in facts if str(fact).strip()),
        )

    title = str(site.get("title", "")).strip()
    description = str(site.get("description", "")).strip()
    return SiteContent(
        title=title or None,
        description=description or None,
        flowers=flowers,
    )


def sync_site_content(
    path: Path,
    rows: list[dict[str, str]],
    default_title: str,
    default_description: str,
) -> None:
    raw = _load_site_content_raw(path)
    site = raw.get("site", {})
    existing_flowers = raw.get("flowers", {})
    if not isinstance(existing_flowers, dict):
        raise SystemExit("Invalid site content: expected [flowers] tables.")

    genera = _manifest_genera(rows)
    rendered = _render_site_content_toml(site, existing_flowers, genera, default_title, default_description)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing != rendered:
        _write_text(path, rendered)
        print(f"Synced {path} with {len(genera)} manifest genera.")


def _load_site_content_raw(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("rb") as content_file:
        return tomllib.load(content_file)


def _manifest_genera(rows: list[dict[str, str]]) -> list[str]:
    genera = {
        (row.get("bucket_genus") or "").strip()
        for row in rows
        if (row.get("bucket_genus") or "").strip()
    }
    if not genera:
        raise SystemExit("No bucketed flowers found in manifest.")
    return sorted(genera)


def _render_site_content_toml(
    site: dict,
    existing_flowers: dict,
    genera: list[str],
    default_title: str,
    default_description: str,
) -> str:
    title = str(site.get("title", default_title)).strip()
    description = str(site.get("description", default_description)).strip()
    lines = [
        "[site]",
        f"title = {_toml_string(title)}",
        f"description = {_toml_string(description)}",
        "",
    ]

    for genus in genera:
        values = existing_flowers.get(genus, {})
        if not isinstance(values, dict):
            raise SystemExit(f"Invalid site content for flowers.{genus}: expected a table.")

        facts = values.get("facts", [])
        if not isinstance(facts, list):
            raise SystemExit(f"Invalid facts for flowers.{genus}: expected a list of strings.")

        lines.extend(
            [
                f"[flowers.{_toml_key(genus)}]",
                f"common_name = {_toml_string(str(values.get('common_name', '')).strip())}",
                f"cover_photo = {_toml_string(str(values.get('cover_photo', '')).strip())}",
                _render_facts_toml(facts),
                "",
            ]
        )

    return "\n".join(lines)


def _render_facts_toml(facts: list) -> str:
    cleaned = [str(fact).strip() for fact in facts if str(fact).strip()]
    if not cleaned:
        return "facts = []"

    lines = ["facts = ["]
    lines.extend(f"  {_toml_string(fact)}," for fact in cleaned)
    lines.append("]")
    return "\n".join(lines)


def _toml_string(value: str) -> str:
    escaped = (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def _toml_key(value: str) -> str:
    return _toml_string(value)


def _build_flowers(
    rows: list[dict[str, str]],
    bucket_root: Path,
    output_dir: Path,
    content: SiteContent,
) -> list[Flower]:
    if not bucket_root.exists():
        raise SystemExit(f"Bucket root does not exist: {bucket_root}")

    rows_by_genus: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        genus = (row.get("bucket_genus") or "").strip()
        relative_path = (row.get("bucket_relative_path") or "").strip()
        if not genus or not relative_path:
            continue
        rows_by_genus.setdefault(genus, []).append(row)

    if not rows_by_genus:
        raise SystemExit("No bucketed flowers found in manifest.")

    flowers = []
    for genus in sorted(rows_by_genus):
        genus_rows = sorted(rows_by_genus[genus], key=lambda row: row.get("bucket_relative_path", ""))
        genus_content = content.flowers.get(genus, FlowerContent(genus, "", ()))
        photos = tuple(
            _make_photo(row, bucket_root, output_dir)
            for row in genus_rows
        )
        cover = _find_cover(genus, photos, genus_content.cover_photo)
        flowers.append(
            Flower(
                genus=genus,
                common_name=genus_content.common_name,
                cover=cover,
                photos=photos,
                facts=genus_content.facts,
                page_url=f"flowers/{_slugify(genus)}.html",
            )
        )

    return flowers


def _make_photo(row: dict[str, str], bucket_root: Path, output_dir: Path) -> Photo:
    filename = row.get("filename", "")
    genus = row.get("bucket_genus", "")
    relative_path = Path(row.get("bucket_relative_path", ""))
    source_path = bucket_root / relative_path
    if not source_path.exists():
        raise SystemExit(f"Manifest image is missing from bucket root: {relative_path}")

    asset_stem = _asset_stem(relative_path)
    genus_slug = _slugify(genus)
    thumb_url = f"assets/images/{genus_slug}/{asset_stem}-thumb.jpg"
    large_url = f"assets/images/{genus_slug}/{asset_stem}-large.jpg"

    if (output_dir / thumb_url) == source_path or (output_dir / large_url) == source_path:
        raise SystemExit(f"Refusing to overwrite source image: {source_path}")

    return Photo(
        filename=filename,
        genus=genus,
        relative_path=relative_path,
        source_path=source_path,
        thumb_url=thumb_url,
        large_url=large_url,
    )


def _find_cover(genus: str, photos: tuple[Photo, ...], cover_photo: str) -> Photo:
    if not cover_photo:
        return photos[0]

    matches = [
        photo
        for photo in photos
        if cover_photo in {photo.filename, photo.relative_path.as_posix()}
    ]
    if not matches:
        raise SystemExit(f"Cover photo for {genus} is not present in manifest: {cover_photo}")
    if len(matches) > 1:
        raise SystemExit(f"Cover photo for {genus} is ambiguous; use bucket_relative_path: {cover_photo}")
    return matches[0]


def _write_resized_image(source_path: Path, destination: Path, size: tuple[int, int]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(destination, "JPEG", quality=84, optimize=True, progressive=True)


def _render_index(flowers: list[Flower], title: str, description: str) -> str:
    cards = "\n".join(_render_card(flower) for flower in flowers)
    intro = f"<p>{_escape(description)}</p>" if description else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(title)}</title>
  <link rel="stylesheet" href="assets/site.css">
</head>
<body>
  <header class="site-header">
    <p class="eyebrow">Flower gallery</p>
    <h1>{_escape(title)}</h1>
    {intro}
  </header>
  <main class="grid">
    {cards}
  </main>
</body>
</html>
"""


def _render_card(flower: Flower) -> str:
    facts = _render_facts(flower.facts)
    return f"""<article class="flower-card">
      <a href="{_url(flower.page_url)}" class="cover-link" aria-label="View all {_escape(flower.genus)} photos">
        <img src="{_url(flower.cover.thumb_url)}" alt="{_escape(flower.common_name)} cover photo" loading="lazy">
      </a>
      <div class="flower-card-body">
        <p class="genus">{_escape(flower.genus)}</p>
        <h2>{_escape(flower.common_name)}</h2>
        {facts}
      </div>
    </article>"""


def _render_flower_page(flower: Flower, site_title: str) -> str:
    photos = "\n".join(
        f"""      <a href="../{_url(photo.large_url)}">
        <img src="../{_url(photo.thumb_url)}" alt="{_escape(flower.common_name)} photo" loading="lazy">
      </a>"""
        for photo in flower.photos
    )
    facts = _render_facts(flower.facts)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(flower.common_name)} - {_escape(site_title)}</title>
  <link rel="stylesheet" href="../assets/site.css">
</head>
<body>
  <header class="site-header">
    <p><a href="../index.html">Back to all flowers</a></p>
    <p class="eyebrow">{_escape(flower.genus)}</p>
    <h1>{_escape(flower.common_name)}</h1>
    {facts}
  </header>
  <main class="photo-grid">
{photos}
  </main>
</body>
</html>
"""


def _render_facts(facts: tuple[str, ...]) -> str:
    if not facts:
        return ""
    items = "\n".join(f"<li>{_escape(fact)}</li>" for fact in facts)
    return f"<ul class=\"facts\">\n{items}\n</ul>"


def _render_css() -> str:
    return """* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #faf7f1;
  color: #263126;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

a {
  color: inherit;
}

.site-header {
  margin: 0 auto;
  max-width: 1120px;
  padding: 48px 24px 24px;
}

.site-header h1 {
  margin: 8px 0 12px;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(2.25rem, 6vw, 5rem);
  line-height: 0.95;
}

.site-header p {
  max-width: 720px;
  color: #5e6a5c;
  font-size: 1.05rem;
  line-height: 1.6;
}

.eyebrow,
.genus {
  color: #6d7d45;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.grid {
  display: grid;
  gap: 24px;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  margin: 0 auto;
  max-width: 1120px;
  padding: 24px;
}

.flower-card {
  overflow: hidden;
  background: #fffefb;
  border: 1px solid #ece3d4;
  border-radius: 22px;
  box-shadow: 0 18px 40px rgba(72, 55, 37, 0.08);
}

.cover-link {
  display: block;
}

img {
  display: block;
  height: auto;
  width: 100%;
}

.flower-card img {
  aspect-ratio: 4 / 3;
  object-fit: cover;
}

.flower-card-body {
  padding: 20px;
}

.flower-card h2 {
  margin: 4px 0 12px;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.7rem;
}

.facts {
  color: #4d5a4c;
  line-height: 1.5;
  margin: 12px 0 0;
  padding-left: 20px;
}

.photo-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 360px));
  justify-content: center;
  margin: 0 auto;
  max-width: 1120px;
  padding: 24px;
}

.photo-grid a {
  overflow: hidden;
  background: #fffefb;
  border-radius: 18px;
  box-shadow: 0 14px 32px rgba(72, 55, 37, 0.08);
}

.photo-grid img {
  aspect-ratio: 4 / 3;
  object-fit: cover;
}
"""


def _ensure_safe_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    cwd = Path.cwd().resolve()
    try:
        relative = resolved.relative_to(cwd)
    except ValueError:
        raise SystemExit(f"Site output_dir must be inside the project directory: {output_dir}") from None
    if not relative.parts:
        raise SystemExit("Site output_dir cannot be the project directory.")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _asset_stem(relative_path: Path) -> str:
    digest = hashlib.sha1(relative_path.as_posix().encode("utf-8")).hexdigest()[:8]
    return f"{_slugify(relative_path.stem)}-{digest}"


def _slugify(value: str) -> str:
    slug = "".join(character if character.isalnum() else "-" for character in value.strip().lower())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "item"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _url(value: str) -> str:
    return quote(value, safe="/:#")

