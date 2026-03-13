#!/usr/bin/env python3
"""
Design Forge — Main Entry Point
Usage:
  python3 forge.py "Your product description here"
  python3 forge.py "CLI tool to optimize CSS" --theme telegraph --out /tmp/out.html
  python3 forge.py list
"""

import os
import sys
import re
import json
import time
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from generator.ai_generator import generate_content
from generator.template_engine import render
from deploy.v2app import deploy, list_landings


def slugify(text: str) -> str:
    """Convert product name to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text[:40].strip('-')
    timestamp = time.strftime("%m%d-%H%M")
    return f"{text}-{timestamp}"


def forge(
    description: str,
    theme: str = "telegraph",
    api_key: str = None,
    provider: str = "auto",
    deploy_live: bool = True,
    out_file: str = None,
    verbose: bool = False,
    content_json: str = None,
) -> dict:
    """
    Full pipeline: description → AI content → HTML → deploy → URL.
    Returns dict with keys: url, slug, html, content

    content_json: path to pre-generated JSON file (skips AI generation)
    """

    # Step 1: Generate or load content
    if content_json:
        # Load pre-generated content (e.g. written by Claude directly)
        with open(content_json, "r", encoding="utf-8") as f:
            content = json.load(f)
        if verbose:
            print(f"📄 Loaded content: {content.get('product_name', '?')}", file=sys.stderr)
    else:
        if verbose:
            print("🔮 Generating content with AI...", file=sys.stderr)
        content = generate_content(description, provider=provider, api_key=api_key)

    if verbose:
        print(f"✅ Content ready: {content.get('product_name', '?')}", file=sys.stderr)
        print("🎨 Rendering HTML template...", file=sys.stderr)

    # Step 2: Render HTML
    html = render(content, theme=theme)

    if verbose:
        print(f"✅ HTML rendered ({len(html)} chars)", file=sys.stderr)

    # Step 2.5: Validate quality
    warnings = _validate_html(html)
    if warnings:
        print("⚠️  QUALITY WARNINGS:", file=sys.stderr)
        for w in warnings:
            print(f"   {w}", file=sys.stderr)

    # Step 3: Optionally save to file
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(html)
        if verbose:
            print(f"💾 Saved to {out_file}", file=sys.stderr)

    # Step 4: Deploy
    url = None
    slug = None
    if deploy_live:
        product_name = content.get("product_name", "product")
        slug = slugify(product_name)
        if verbose:
            print(f"🚀 Deploying as {slug}...", file=sys.stderr)
        url = deploy(html, slug)
        if verbose:
            print(f"🌐 Live at: {url}", file=sys.stderr)

    return {
        "url": url,
        "slug": slug,
        "html": html,
        "content": content,
    }


def _validate_html(html: str) -> list:
    """Check generated HTML for quality issues. Returns list of warning strings."""
    import unicodedata
    warnings = []

    # 1. Check for emoji (Unicode category So/Sm with high codepoints)
    emoji_found = []
    for i, ch in enumerate(html):
        cp = ord(ch)
        if (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF):
            emoji_found.append(ch)
    if emoji_found:
        unique = list(set(emoji_found))[:8]
        warnings.append(f"❌ EMOJI DETECTED: {''.join(unique)} — replace with SVG icons")

    # 2. Check for SMIL <animate> tags
    if re.search(r'<animate\s', html, re.IGNORECASE):
        warnings.append("❌ SMIL <animate> TAG FOUND — iOS Safari does not support SMIL. Use CSS keyframes.")

    # 3. Check for spinning conic-gradient (the "screw" effect)
    if re.search(r'conic-gradient.*animation.*rotate|animation.*rotate.*conic-gradient', html, re.IGNORECASE | re.DOTALL):
        warnings.append("⚠️  SPINNING CONIC-GRADIENT detected — looks like a screw, use shimmer instead")

    # 4. Check overflow-x is set
    if 'overflow-x:hidden' not in html.replace(' ', '') and 'overflow-x: hidden' not in html:
        warnings.append("⚠️  overflow-x:hidden NOT FOUND on html/body — may cause horizontal scroll on mobile")

    # 5. Check SVG keyframes are injected
    if 'svgPulse' not in html and 'svgFloat' not in html:
        warnings.append("⚠️  SVG keyframes not found — icons may have no animation")

    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Design Forge — AI landing page generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 forge.py "CLI tool to optimize CSS bundle size"
  python3 forge.py "SaaS analytics for developers" --theme telegraph --verbose
  python3 forge.py "My product" --no-deploy --out landing.html
  python3 forge.py list
        """
    )
    parser.add_argument("description", nargs="?", help="Product description (or 'list')")
    parser.add_argument("--theme", default="telegraph", help="Template theme (default: telegraph)")
    parser.add_argument("--provider", default="auto", choices=["auto", "claude", "groq", "openai"], help="AI provider (default: auto-detect from env)")
    parser.add_argument("--api-key", help="AI API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--from-json", help="Use pre-generated content JSON file (skip AI)")
    parser.add_argument("--no-deploy", action="store_true", help="Don't deploy, just generate HTML")
    parser.add_argument("--out", help="Save HTML to this file")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of plain text")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress")

    args = parser.parse_args()

    if not args.description:
        parser.print_help()
        sys.exit(0)

    if args.description == "list":
        landings = list_landings()
        if not landings:
            print("No landings yet.")
        else:
            for l in landings:
                print(f"{l['url']}  ({l['slug']})")
        return

    try:
        result = forge(
            description=args.description or "",
            theme=args.theme,
            api_key=args.api_key,
            provider=args.provider,
            deploy_live=not args.no_deploy,
            out_file=args.out,
            verbose=args.verbose,
            content_json=args.from_json,
        )

        if args.json:
            # Don't include full HTML in JSON output (too large)
            output = {
                "url": result["url"],
                "slug": result["slug"],
                "product_name": result["content"].get("product_name"),
                "tagline": f"{result['content'].get('tagline_line1')} {result['content'].get('tagline_line2')}",
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            if result["url"]:
                print(result["url"])
            elif args.out:
                print(f"Saved to {args.out}")
            else:
                print(result["html"])

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
